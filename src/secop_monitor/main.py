import argparse
import logging
import datetime
import sys

from src.secop_monitor.config import load_config
from src.secop_monitor.repository import Repository
from src.secop_monitor.collectors import get_collector
from src.secop_monitor.normalize import normalize_item
from src.secop_monitor.matcher import evaluate_best_match
from src.secop_monitor.dedupe import is_secondary_duplicate
from src.secop_monitor.notifier import get_notifier
from src.secop_monitor.models import Opportunity

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def command_init_db(config_path: str):
    config = load_config(config_path)
    repo = Repository(config.app.db_url)
    repo.create_tables()
    logger.info("Base de datos y tablas inicializadas con éxito.")

def command_run(config_path: str):
    config = load_config(config_path)
    repo = Repository(config.app.db_url)
    repo.create_tables() # Safe to call always
    
    collector = get_collector(config)
    notifier = get_notifier(config)
    
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    since_utc = now_utc - datetime.timedelta(days=config.filters.published_within_days)
    
    with repo.get_session() as session:
        run = repo.create_run(session, config.source.collector)
        
        items_collected = 0
        items_after_filters = 0
        items_new = 0
        
        try:
            logger.info("Extrayendo de Collector...")
            raw_items = collector.collect(since_utc, config.app.max_items_per_run)
            items_collected = len(raw_items)
            
            # Filtro básico (MVP)
            valid_raw_items = []
            for item in raw_items:
                if config.filters.min_budget and (item.budget is None or item.budget < config.filters.min_budget):
                    continue
                if config.filters.entity_allowlist and item.entity_name not in config.filters.entity_allowlist:
                    continue
                valid_raw_items.append(item)
                
            items_after_filters = len(valid_raw_items)
            
            # Pre-calc N+1 Process Ids Filter
            all_process_ids = [i.process_id for i in valid_raw_items]
            existing_ids = repo.get_existing_process_ids(session, all_process_ids)
            
            # Contexto para dedupe secundario: DB items recientes
            recent_opps = list(repo.get_recent_opportunities(session, since_utc))
            
            new_opportunities = []
            
            for raw in valid_raw_items:
                if raw.process_id in existing_ids:
                    continue  # Ya existe primario, idempotencia rápida
                    
                norm_item = normalize_item(raw)
                best_query_name, match_result = evaluate_best_match(
                    norm_item, config.queries, config.app.score_threshold
                )
                
                # Determinación de status
                if match_result.matched:
                    if is_secondary_duplicate(norm_item, recent_opps, 0.90):
                        status = "dismissed" # Republicación con nuevo ID, ignorar alerta
                    else:
                        status = "new"       # Alerta encolada
                else:
                    status = "saved"         # No matchea suficientes keywords
                    
                opp = Opportunity(
                    source_system="SECOP",
                    process_id=raw.process_id,
                    title=norm_item.raw.title,
                    entity_name=norm_item.raw.entity_name,
                    description=norm_item.raw.description,
                    published_at=norm_item.raw.published_at,
                    closing_at=norm_item.raw.closing_at,
                    budget=norm_item.raw.budget,
                    location=norm_item.raw.location,
                    url=norm_item.raw.url,
                    query_match=best_query_name,
                    score=match_result.score,
                    match_explain=match_result.explain,
                    status=status,
                    fingerprint=norm_item.fingerprint
                )
                
                new_opportunities.append(opp)
                # Mantener lista actualizada en memoria para no duplicarnos dentro del mismo run
                recent_opps.append(opp) 
                
                if status == "new":
                    items_new += 1
                    
            logger.info(f"Guardando {len(new_opportunities)} nuevas oportunidades en DB ({items_new} alertas para notificar).")
            repo.save_opportunities(session, new_opportunities)
            
            # Extraer pendientes limitados a `max_alerts_per_run` global
            pending_opps = repo.get_pending_notifications(session, limit=config.notifications.max_alerts_per_run) 
            items_notified = len(pending_opps)
            
            if items_notified > 0:
                notifier.notify(pending_opps)
                repo.mark_as_notified(session, [o.id for o in pending_opps])
                
            repo.finish_run(
                session, run, 
                items_collected=items_collected, 
                items_after_filters=items_after_filters,
                items_new=items_new,
                items_notified=items_notified
            )
            
            session.commit()
            logger.info("Pipeline finalizado satisfactoriamente.")
            
        except Exception as e:
            session.rollback()
            # Reaprovechar la misma instancia o ID del run fallido local para documentarlo en BD 
            with repo.get_session() as error_session:
                error_session.add(run)
                repo.finish_run(
                     error_session, run, 
                     items_collected, items_after_filters, 0, 0, 
                     errors=[str(e)]
                )
                error_session.commit()
                 
            logger.exception("Error crítico, pipeline interrumpido y rollback ejecutado.")
            sys.exit(1)

def command_show_latest(config_path: str, n: int):
    config = load_config(config_path)
    repo = Repository(config.app.db_url)
    
    with repo.get_session() as session:
        pending = repo.get_pending_notifications(session, limit=n)
        for opp in pending:
            print(f"[{opp.score:.2f}] {opp.title} ({opp.process_id}) - {opp.status}")
            
def main():
    parser = argparse.ArgumentParser(description="SECOP Monitor Pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    init_parser = subparsers.add_parser("init-db")
    init_parser.add_argument("--config", default="./config.yaml", help="Ruta al config.yaml")
    
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--config", default="./config.yaml", help="Ruta al config.yaml")
    
    show_parser = subparsers.add_parser("show-latest")
    show_parser.add_argument("--config", default="./config.yaml", help="Ruta al config.yaml")
    show_parser.add_argument("--n", type=int, default=20, help="Número de items a mostrar")
    
    args = parser.parse_args()
    
    if args.command == "init-db":
        command_init_db(args.config)
    elif args.command == "run":
        command_run(args.config)
    elif args.command == "show-latest":
        command_show_latest(args.config, args.n)

if __name__ == "__main__":
    main()

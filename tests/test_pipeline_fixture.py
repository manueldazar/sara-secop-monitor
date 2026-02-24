import os
import pytest
from sqlalchemy import select

from src.secop_monitor.config import load_config
from src.secop_monitor.main import command_run, command_init_db
from src.secop_monitor.repository import Repository
from src.secop_monitor.models import Opportunity, Run

@pytest.fixture
def test_db_path(tmp_path):
    """Establece una DB temporal."""
    # Create test specific config file
    db_file = tmp_path / "test_secop.db"
    config_file = tmp_path / "test_config.yaml"
    
    # Base YAML contents (referencing our actual data/fixtures)
    yaml_content = f"""
app:
  db_url: "sqlite:///{db_file}"
  timezone: "America/Bogota"
  notifier: "stdout"
  score_threshold: 0.65
  max_items_per_run: 50

source:
  collector: "fixture"
  fixture_path: "{os.path.abspath('data/fixtures/secop_items.json')}"

filters:
  published_within_days: 1000

queries:
  - name: "IA-LLM"
    keywords_any: ["inteligencia artificial", "ia", "llm", "modelo de lenguaje"]
    keywords_all: []
    keywords_not: ["mantenimiento", "aseo", "papelería", "papeleria"]
    phrases: ["modelo de lenguaje"]
    synonyms: {{}}
    
  - name: "Data-Analytics"
    keywords_any: ["analitica", "data warehouse", "bi"]

notifications:
  max_alerts_per_run: 5
  slack:
    webhook_env_var: "SLACK"
    username: "bot"
"""
    with open(config_file, "w") as f:
        f.write(yaml_content)
        
    return str(config_file), f"sqlite:///{db_file}"

def test_full_pipeline_workflow(test_db_path):
    config_path, db_url = test_db_path
    
    # 0. Inicializar la base de datos
    command_init_db(config_path)
    repo = Repository(db_url)
    
    # ==========================
    # CORRIDA 1: Ingesta inicial
    # ==========================
    command_run(config_path)
    
    with repo.get_session() as session:
        # A) Checks sobre persistencia y conteos
        runs = session.scalars(select(Run)).all()
        assert len(runs) == 1
        
        run1 = runs[0]
        assert run1.items_collected == 6  # 6 fixtures in JSON
        assert run1.items_after_filters == 6
        # Solo matchean IA-LLM (2 id de tech + 1 republish = 3) y Analytics (1) pero config_threshold es 0.65
        # SECOP-001 (IA), SECOP-003 (Analytics), SECOP-004 (IA), SECOP-DUP-001(Republish)
        # SECOP-002 es ruido (aseo), SECOP-NOISE-99 es papeleria
        
        opportunities = session.scalars(select(Opportunity)).all()
        assert len(opportunities) == 6 # Todos se persisten, algunos como 'saved'
        
        # B) Comportamiento Dedupe secundario:
        # SECOP-DUP-001 debe ser status 'dismissed' ya que colisiona con el titulo de SECOP-001
        dup_opp = session.scalars(select(Opportunity).where(Opportunity.process_id == "SECOP-DUP-001")).first()
        assert dup_opp is not None
        assert dup_opp.status == "dismissed"
        
        # C) Comportamiento Excluido / Sin keywords:
        # SECOP-NOISE-99 y SECOP-002 no tienen keywords/fueron excluidos en la Principal, se quedan por debajo del threshold (0.65)
        noise_opp = session.scalars(select(Opportunity).where(Opportunity.process_id == "SECOP-002")).first()
        assert noise_opp.status == "saved"
        assert noise_opp.score < 0.65
        
        # D) Notificaciones Limitadas
        # El status "notified" se lo llevan los aprobados
        notified_opps = session.scalars(select(Opportunity).where(Opportunity.status == "notified")).all()
        # SECOP-001, SECOP-003 superan 0.65 de score
        assert len(notified_opps) > 0

    # ==========================
    # CORRIDA 2: Idempotencia
    # ==========================
    command_run(config_path)
    
    with repo.get_session() as session:
        runs = session.scalars(select(Run)).all()
        assert len(runs) == 2
        
        run2 = runs[1]
        assert run2.items_collected == 6
        assert run2.items_new == 0 # Nada nuevo que alertar
        assert run2.items_notified == 0
        
        opps_count = session.query(Opportunity).count()
        assert opps_count == 6 # Evitamos duplicaciones completas

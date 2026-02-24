import datetime
import logging
import pytz
from typing import Any, Sequence

from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from src.secop_monitor.models import Base, Opportunity, Run

logger = logging.getLogger(__name__)

class Repository:
    """Manejo de acceso a datos para Opportunities y Runs."""
    
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
    def create_tables(self) -> None:
        """Crea las tablas en la DB según los modelos."""
        Base.metadata.create_all(bind=self.engine)

    def get_session(self) -> Session:
        return self.SessionLocal()

    def get_existing_process_ids(self, session: Session, process_ids: list[str]) -> set[str]:
        """Devuelve un set con los process_ids que ya existen en la BD en una sola query."""
        if not process_ids:
            return set()
            
        stmt = select(Opportunity.process_id).where(Opportunity.process_id.in_(process_ids))
        result = session.scalars(stmt).all()
        return set(result)

    def save_opportunities(self, session: Session, items: list[Opportunity]) -> None:
        """Persiste una lista de nuevas oportunidades, ignorando duplicados si pasan el pre-filtro."""
        for item in items:
            try:
                # El begin_nested crea un SAVEPOINT nativo a nivel BD permitiendo
                # hacer rollback en caso de IntegrityError específico de ese item sin romper
                # toda la transacción original de la DB (pipeline batch rollback).
                with session.begin_nested():
                    session.add(item)
                    session.flush()
            except IntegrityError:
                logger.warning(
                    f"IntegrityError: process_id='{item.process_id}' ya existe o quiebra restricción. Omitido."
                )

    def create_run(self, session: Session, collector_name: str) -> Run:
        run = Run(
            started_at=datetime.datetime.now(datetime.timezone.utc),
            collector=collector_name
        )
        session.add(run)
        session.flush()
        return run

    def finish_run(
        self, 
        session: Session, 
        run: Run, 
        items_collected: int,
        items_after_filters: int,
        items_new: int,
        items_notified: int,
        errors: list[Any] | None = None
    ) -> None:
        run.finished_at = datetime.datetime.now(datetime.timezone.utc)
        run.items_collected = items_collected
        run.items_after_filters = items_after_filters
        run.items_new = items_new
        run.items_notified = items_notified
        run.errors = errors
        session.flush()
        
    def get_pending_notifications(self, session: Session, limit: int = 20) -> Sequence[Opportunity]:
        stmt = (
            select(Opportunity)
            .where(Opportunity.status == "new")
            .order_by(Opportunity.score.desc())
            .limit(limit)
        )
        return session.scalars(stmt).all()
        
    def get_recent_opportunities(self, session: Session, since: datetime.datetime) -> Sequence[Opportunity]:
        """Obtiene las oportunidades desde una fecha dada para deduplicación secundaria."""
        stmt = select(Opportunity).where(Opportunity.published_at >= since)
        return session.scalars(stmt).all()
        
    def mark_as_notified(self, session: Session, opportunity_ids: list[int]) -> None:
        if not opportunity_ids:
            return
            
        stmt = (
            update(Opportunity)
            .where(Opportunity.id.in_(opportunity_ids))
            .values(
                status="notified", 
                updated_at=datetime.datetime.now(datetime.timezone.utc)
            )
        )
        session.execute(stmt)

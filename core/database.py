from datetime import date, datetime
from typing import Optional

from sqlalchemy import create_engine, desc, and_, update
from sqlalchemy.orm import Session, sessionmaker

from core.models import (
    Base,
    Security,
    ConstituentSet,
    ConstituentMember,
    DailyPrice,
    PipelineRun,
    IndexValue,
    RunStatus,
)


class DatabaseManager:
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, pool_pre_ping=True, pool_size=5)
        self.session_factory = sessionmaker(bind=self.engine)

    def get_session(self) -> Session:
        return self.session_factory()

    def create_tables(self) -> None:
        Base.metadata.create_all(self.engine)

    def get_security_by_symbol(self, session: Session, symbol: str) -> Optional[Security]:
        return session.query(Security).filter(Security.symbol == symbol.upper()).first()

    def get_or_create_security(self, session: Session, symbol: str, name: str) -> Security:
        security = self.get_security_by_symbol(session, symbol)
        if not security:
            security = Security(symbol=symbol.upper(), name=name)
            session.add(security)
            session.flush()
        return security

    def get_active_constituents(self, session: Session, as_of_date: date) -> list[str]:
        result = (
            session.query(Security.symbol)
            .join(ConstituentMember, ConstituentMember.security_id == Security.id)
            .join(ConstituentSet, ConstituentSet.id == ConstituentMember.constituent_set_id)
            .filter(ConstituentSet.effective_from <= as_of_date)
            .filter(
                (ConstituentSet.effective_to.is_(None))
                | (ConstituentSet.effective_to >= as_of_date)
            )
            .all()
        )
        return [r[0] for r in result]

    def get_previous_prices(self, session: Session, business_date: date) -> dict[str, float]:
        subquery = (
            session.query(DailyPrice)
            .filter(DailyPrice.date < business_date)
            .order_by(DailyPrice.date.desc())
            .limit(500)
            .subquery()
        )
        results = (
            session.query(Security.symbol, DailyPrice.close_price)
            .join(DailyPrice, DailyPrice.security_id == Security.id)
            .filter(DailyPrice.date < business_date)
            .order_by(DailyPrice.date.desc())
            .all()
        )
        prices = {}
        for symbol, close in results:
            if symbol not in prices:
                prices[symbol] = close
        return prices

    def get_previous_index_level(self, session: Session, business_date: date) -> Optional[float]:
        result = (
            session.query(IndexValue.index_level)
            .filter(IndexValue.business_date < business_date)
            .filter(IndexValue.is_current.is_(True))
            .order_by(IndexValue.business_date.desc())
            .first()
        )
        return result[0] if result else None

    def create_run(
        self,
        session: Session,
        run_id: str,
        business_date: date,
        file_checksum: Optional[str] = None,
        code_version: Optional[str] = None,
    ) -> PipelineRun:
        run = PipelineRun(
            run_id=run_id,
            business_date=business_date,
            file_checksum=file_checksum,
            status=RunStatus.PENDING.value,
            code_version=code_version,
        )
        session.add(run)
        session.flush()
        return run

    def update_run_status(
        self,
        session: Session,
        run_id: str,
        status: RunStatus,
        error_message: Optional[str] = None,
    ) -> None:
        run = session.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()
        if run:
            run.status = status.value
            if status in (RunStatus.COMPLETED, RunStatus.FAILED):
                run.finished_at = datetime.utcnow()
            if error_message:
                run.error_message = error_message
            session.flush()

    def check_duplicate_run(self, session: Session, business_date: date, file_checksum: str) -> bool:
        existing = (
            session.query(PipelineRun)
            .filter(
                PipelineRun.business_date == business_date,
                PipelineRun.file_checksum == file_checksum,
                PipelineRun.status == RunStatus.COMPLETED.value,
            )
            .first()
        )
        return existing is not None

    def load_prices(
        self,
        session: Session,
        business_date: date,
        prices_data: list[dict],
        source_file: str,
    ) -> int:
        count = 0
        for row in prices_data:
            symbol = row["symbol"].upper()
            security = self.get_or_create_security(session, symbol, symbol)
            existing = (
                session.query(DailyPrice)
                .filter(DailyPrice.date == business_date, DailyPrice.security_id == security.id)
                .first()
            )
            if existing:
                existing.open_price = row["open"]
                existing.high_price = row["high"]
                existing.low_price = row["low"]
                existing.close_price = row["close"]
                existing.volume = row.get("volume", 0)
                existing.vwap = row.get("vwap")
                existing.source_file = source_file
            else:
                price = DailyPrice(
                    date=business_date,
                    security_id=security.id,
                    open_price=row["open"],
                    high_price=row["high"],
                    low_price=row["low"],
                    close_price=row["close"],
                    volume=row.get("volume", 0),
                    vwap=row.get("vwap"),
                    source_file=source_file,
                )
                session.add(price)
            count += 1
        session.flush()
        return count

    def supersede_previous_index(self, session: Session, business_date: date) -> int:
        result = (
            session.query(IndexValue)
            .filter(
                IndexValue.business_date == business_date,
                IndexValue.is_current.is_(True),
            )
            .update({IndexValue.is_current: False})
        )
        session.flush()
        return result

    def save_index_value(
        self,
        session: Session,
        business_date: date,
        index_level: float,
        daily_return: Optional[float],
        constituent_count: int,
        run_id: str,
    ) -> IndexValue:
        self.supersede_previous_index(session, business_date)
        index_value = IndexValue(
            business_date=business_date,
            index_level=index_level,
            daily_return=daily_return,
            constituent_count=constituent_count,
            run_id=run_id,
            is_current=True,
        )
        session.add(index_value)
        session.flush()
        return index_value

    def get_latest_index_value(self, session: Session) -> Optional[IndexValue]:
        return (
            session.query(IndexValue)
            .filter(IndexValue.is_current.is_(True))
            .order_by(IndexValue.business_date.desc())
            .first()
        )

    def get_index_values_range(
        self,
        session: Session,
        start_date: date,
        end_date: date,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[IndexValue], int]:
        query = (
            session.query(IndexValue)
            .filter(
                IndexValue.is_current.is_(True),
                IndexValue.business_date >= start_date,
                IndexValue.business_date <= end_date,
            )
            .order_by(IndexValue.business_date)
        )
        total = query.count()
        offset = (page - 1) * page_size
        values = query.offset(offset).limit(page_size).all()
        return values, total

    def get_index_value_by_run(self, session: Session, run_id: str) -> list[IndexValue]:
        return (
            session.query(IndexValue)
            .filter(IndexValue.run_id == run_id)
            .order_by(IndexValue.business_date)
            .all()
        )

    def list_runs(
        self,
        session: Session,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[PipelineRun], int]:
        query = session.query(PipelineRun).order_by(PipelineRun.started_at.desc())
        total = query.count()
        offset = (page - 1) * page_size
        runs = query.offset(offset).limit(page_size).all()
        return runs, total

    def get_run_by_id(self, session: Session, run_id: str) -> Optional[PipelineRun]:
        return session.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()

    def get_constituents_for_date(self, session: Session, as_of_date: date) -> list[dict]:
        results = (
            session.query(Security.symbol, Security.name, ConstituentSet.version)
            .join(ConstituentMember, ConstituentMember.security_id == Security.id)
            .join(ConstituentSet, ConstituentSet.id == ConstituentMember.constituent_set_id)
            .filter(ConstituentSet.effective_from <= as_of_date)
            .filter(
                (ConstituentSet.effective_to.is_(None))
                | (ConstituentSet.effective_to >= as_of_date)
            )
            .order_by(Security.symbol)
            .all()
        )
        return [
            {"symbol": r[0], "name": r[1], "set_version": r[2]}
            for r in results
        ]

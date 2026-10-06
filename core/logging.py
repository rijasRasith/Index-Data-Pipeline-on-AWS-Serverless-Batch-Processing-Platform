import json
import uuid
from datetime import datetime

import structlog


def configure_logging(level: str = "INFO") -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            structlog.get_level_from_name(level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)


def generate_correlation_id() -> str:
    return str(uuid.uuid4())


def generate_run_id() -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    short_id = uuid.uuid4().hex[:8]
    return f"run-{timestamp}-{short_id}"


class PipelineLogContext:
    def __init__(self, correlation_id: str, business_date: str, stage: str):
        self.correlation_id = correlation_id
        self.business_date = business_date
        self.stage = stage
        self.logger = get_logger(stage)

    def bind(self, **kwargs: object) -> structlog.BoundLogger:
        return self.logger.bind(
            correlation_id=self.correlation_id,
            business_date=self.business_date,
            stage=self.stage,
            **kwargs,
        )

    def log_event(self, event: str, **kwargs: object) -> None:
        bound = self.bind(**kwargs)
        bound.info(event)

    def log_error(self, event: str, **kwargs: object) -> None:
        bound = self.bind(**kwargs)
        bound.error(event)

    def log_metrics(self, metrics: dict) -> None:
        bound = self.bind(metrics=metrics)
        bound.info("metrics_recorded")

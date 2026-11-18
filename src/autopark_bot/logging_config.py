import logging
import sys

import structlog


def configure_logging(level: str = "INFO", fmt: str = "pretty") -> None:
    """Единый формат для structlog и стандартного logging (aiogram, sqlalchemy и т.д.)."""
    shared: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if fmt == "json":
        shared.append(structlog.processors.dict_tracebacks)
        renderer = structlog.processors.JSONRenderer(
            sort_keys=True, ensure_ascii=False, default=str
        )
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

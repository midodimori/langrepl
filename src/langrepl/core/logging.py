import logging
import warnings
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from rich.logging import RichHandler

from langrepl.core.constants import CONFIG_LOG_DIR
from langrepl.core.settings import settings

# File format includes full context (for log file)
FILE_LOG_FORMAT = (
    "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
)


def configure_logging(show_logs: bool = False, working_dir: Path = Path.cwd()) -> None:
    """Configure application logging.

    Args:
        show_logs: Enable verbose logging (console + file). If False, logs are hidden.
        working_dir: Working directory for log file.
    """
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Suppress langchain warnings
    logging.getLogger("langchain_google_genai._function_utils").setLevel(logging.ERROR)
    logging.getLogger("langchain_anthropic").setLevel(logging.ERROR)
    logging.getLogger("langchain_openai").setLevel(logging.ERROR)

    # Suppress HTTP client loggers (noisy at INFO level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # Suppress checkpointer/database loggers
    logging.getLogger("langgraph.checkpoint.sqlite.aio").setLevel(logging.WARNING)
    logging.getLogger("langgraph.checkpoint").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)

    # Suppress markdown parser debug logs
    logging.getLogger("markdown_it").setLevel(logging.WARNING)

    # Suppress langchain_aws warnings
    warnings.filterwarnings("ignore", module="langchain_aws.chat_models.bedrock")

    # Suppress LangSmith UUID v7 deprecation warning
    warnings.filterwarnings(
        "ignore",
        message="LangSmith now uses UUID v7",
        category=UserWarning,
        module="pydantic.v1.main",
    )

    if show_logs:
        # Pretty console logging with RichHandler (shows file:line automatically)
        console_handler = RichHandler(
            show_time=True,
            show_level=True,
            show_path=True,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
        )
        root_logger.addHandler(console_handler)

        # File logging with daily rotation
        log_dir = working_dir / CONFIG_LOG_DIR
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            file_handler = TimedRotatingFileHandler(
                log_dir / "app.log",
                when="midnight",
                interval=1,
                backupCount=7,  # Keep 7 days of logs
                encoding="utf-8",
            )
            # Rotated files will be named app.log.YYYY-MM-DD
            file_handler.suffix = "%Y-%m-%d"
            file_handler.setFormatter(logging.Formatter(FILE_LOG_FORMAT))
            root_logger.addHandler(file_handler)

            logging.getLogger(__name__).info("Logging initialized")
        except (OSError, PermissionError):
            pass  # Sandbox may block file creation


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name.

    Args:
        name: Logger name

    Returns:
        logging.Logger: Logger
    """
    return logging.getLogger(name)

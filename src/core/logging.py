import logging
import warnings

from src.core.settings import settings

LOG_FORMAT = (
    "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
)


def configure_logging(show_logs: bool = False) -> None:
    """Configure application logging.

    Args:
        show_logs: Whether to show logs on console. If False, logs are hidden by default.
    """
    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)

    # Clear existing handlers
    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)

    # Suppress langchain warnings
    logging.getLogger("langchain_google_genai._function_utils").setLevel(logging.ERROR)
    logging.getLogger("langchain_anthropic").setLevel(logging.ERROR)
    logging.getLogger("langchain_openai").setLevel(logging.ERROR)

    # Suppress langchain_aws warnings
    warnings.filterwarnings("ignore", module="langchain_aws.chat_models.bedrock")

    # Add console handler only if show_logs is True
    if show_logs:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name.

    Args:
        name: Logger name

    Returns:
        logging.Logger: Logger
    """
    return logging.getLogger(name)

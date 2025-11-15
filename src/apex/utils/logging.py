"""
Structured logging configuration with Application Insights integration.
"""
import logging
import sys

from apex.config import config


def setup_logging():
    """
    Configure application logging.

    Integrates with Azure Application Insights if connection string is configured.
    Logs to stdout for container-based deployments.
    """
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Integrate with Application Insights if configured
    if config.AZURE_APPINSIGHTS_CONNECTION_STRING:
        try:
            from opencensus.ext.azure.log_exporter import AzureLogHandler

            logger = logging.getLogger()
            logger.addHandler(
                AzureLogHandler(connection_string=config.AZURE_APPINSIGHTS_CONNECTION_STRING)
            )
        except ImportError:
            logging.warning("opencensus-ext-azure not installed, skipping App Insights integration")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)

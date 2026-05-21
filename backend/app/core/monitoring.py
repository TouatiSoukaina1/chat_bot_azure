import os

from azure.monitor.opentelemetry import configure_azure_monitor


def setup_monitoring() -> None:
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

    if not connection_string:
        return

    configure_azure_monitor(
        connection_string=connection_string
    )
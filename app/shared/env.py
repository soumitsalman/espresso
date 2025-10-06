import os, tomli
import logging
from types import SimpleNamespace
from azure.monitor.opentelemetry import configure_azure_monitor
from app.pybeansack.mongosack import Beansack
from app.shared.embedder import LlamaCppEmbeddings

config: SimpleNamespace = None
db: Beansack = None
embedder = None
logger: logging.Logger = None

def _dict_to_namespace(d):
    """Recursively convert a dictionary to SimpleNamespace."""
    if isinstance(d, dict):
        return SimpleNamespace(**{k: _dict_to_namespace(v) for k, v in d.items()})
    return d

def load_env(*args):
    values = {}
    for arg in args:
        if os.path.exists(arg):
            with open(arg, "rb") as file:
                values.update(tomli.load(file))

    global db, config, embedder, logger

    config = _dict_to_namespace(values)
    db = Beansack(os.getenv('DB_CONNECTION_STRING'), os.getenv('DB_NAME'))
    embedder = LlamaCppEmbeddings(os.getenv('EMBEDDER_PATH'), 512)
    logger = logging.getLogger(config.app.name)

    az_monitoring = os.getenv('APPINSIGHTS_CONNECTION_STRING')
    if az_monitoring:  configure_azure_monitor(
        connection_string=az_monitoring, 
        logger_name=config.app.name, 
        instrumentation_options={"fastapi": {"enabled": True}}
    )  

def log(function, **kwargs):   
    # transform the values before logging for flat tables
    kwargs = {key: (str(value) if isinstance(value, list) else value) for key, value in kwargs.items() if value}
    logger.info(function, extra=kwargs)
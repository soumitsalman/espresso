import logging
import humanize 
from datetime import datetime, timedelta
from urllib.parse import urlparse
import os
import tomli
from types import SimpleNamespace
from sentence_transformers import SentenceTransformer
from pybeansack import Beansack, create_client

config: SimpleNamespace = None
db: Beansack = None
embedder: SentenceTransformer = None

def initialize_app(*args):
    values = {}
    for arg in args:
        if os.path.exists(arg):
            with open(arg, "rb") as file:
                values.update(tomli.load(file))

    global db, config, embedder

    config = _dict_to_namespace(values)
    db = create_client(os.getenv("DB_TYPE"), pg_connection_string=os.getenv("PG_CONNECTION_STRING"), lancedb_storage=os.getenv("LANCEDB_STORAGE"))
    embedder = SentenceTransformer(
        os.getenv('EMBEDDER_MODEL'), 
        tokenizer_kwargs={
            "truncation": True,
            "max_length": int(os.getenv('EMBEDDER_CTX', 512)),
            "padding": True
        }
    )

def read_file(path: str) -> str:
    with open(path, "r") as file: 
        return file.read()
    
def embed_query(query: str):
    import torch
    with torch.inference_mode(), torch.no_grad():
        vec = embedder.encode_query(query, convert_to_numpy=True).tolist()
    return vec


log = lambda msg, **kwargs: logging.info(msg, extra={key: (str(value) if isinstance(value, list) else value) for key, value in kwargs.items() if value})
to_list = lambda x: x if isinstance(x, list) else [x]
is_valid_url = lambda url: urlparse(url).scheme in ["http", "https"]
site_name = lambda bean: bean.publisher.title if bean.publisher and bean.publisher.title else bean.source
favicon = lambda bean: bean.publisher.favicon if bean.publisher and bean.publisher.favicon else f"https://www.google.com/s2/favicons?domain={bean.source}"
naturalday = lambda date_val: humanize.naturalday(date_val, format="%a, %b %d")
naturalnum = humanize.intword

def _dict_to_namespace(d):
    """Recursively convert a dictionary to SimpleNamespace."""
    if isinstance(d, dict):
        return SimpleNamespace(**{k: _dict_to_namespace(v) for k, v in d.items()})
    return d
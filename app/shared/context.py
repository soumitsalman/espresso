import os
import torch
from duckdb import torch
import tomli
from types import SimpleNamespace
from threading import Lock
from celery import Celery
import numpy as np
# from optimum.onnxruntime import ORTModelForFeatureExtraction
# from transformers import AutoTokenizer
from sentence_transformers import SentenceTransformer
from pybeansack import Beansack, create_client
from icecream import ic

_CACHE_DIR = ".models"

class OnnxEmbedder:
    def __init__(self, model_name: str, ctx_len: int):
        self.model_name = model_name
        self.ctx_len = ctx_len
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, cache_dir=_CACHE_DIR)
        self.model = ORTModelForFeatureExtraction.from_pretrained(model_name, cache_dir=_CACHE_DIR, provider="CPUExecutionProvider", export=True)

    def encode_query(self, query: str) -> list[float]:
        inputs = self.tokenizer(query, truncation=True, max_length=self.ctx_len, return_tensors="np")
        outputs = self.model(**inputs)
        embedding = _mean_pooling(outputs.last_hidden_state, inputs["attention_mask"])
        return embedding[0].tolist()

def _mean_pooling(token_embeddings: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
    mask_expanded = np.expand_dims(attention_mask, -1).astype(np.float32)
    sum_embeddings = np.sum(token_embeddings * mask_expanded, axis=1)
    sum_mask = np.clip(np.sum(mask_expanded, axis=1), a_min=1e-9, a_max=None)
    return sum_embeddings / sum_mask

# celery_app = Celery(
#     "espresso",
#     broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
#     backend=os.getenv("CELERY_RESULT_BACKEND") or os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
# )

# @celery_app.task(name="app.shared.context.embed_query_task")
# def embed_query_task(query: str, model_name: str, ctx_len: int) -> list[float]:
#     embedder = _get_embedder(model_name, ctx_len)
#     from icecream import ic
#     return ic(embedder.encode_query(query))

class AppContext:  
    db: Beansack = None
    embedder_settings: dict = None
    settings: dict = None
    embedder = None
    embedder_lock = None

    def __init__(self, db_kwargs: dict, embedder_kwargs: dict = None, **additional_settings_kwargs):               
        self.db = create_client(**db_kwargs)
        self.embedder_settings = embedder_kwargs or {}
        self.settings = additional_settings_kwargs or {}
        self.embedder_lock = Lock()

    def embed_query(self, query: str): 
        with self.embedder_lock:
            if not self.embedder:
                self.embedder = SentenceTransformer(
                    self.embedder_settings.get("model_name"), 
                    tokenizer_kwargs={
                        "truncation": True,
                        "max_length": int(self.embedder_settings.get("ctx_len", 512))
                    }, 
                    cache_folder=_CACHE_DIR
                )
                # self.embedder = OnnxEmbedder(
                #     self.embedder_settings.get("model_name"), 
                #     int(self.embedder_settings.get("ctx_len", 512))
                # )
        return self.embedder.encode_query(query, convert_to_numpy=True).tolist()

    def close(self):
        if self.db: self.db.close()  

def load_settings(settings_file: str) -> SimpleNamespace:
    """Load settings from a TOML file into a SimpleNamespace."""
    _dict_to_namespace = lambda d: SimpleNamespace(**{k: _dict_to_namespace(v) for k, v in d.items()}) if isinstance(d, dict) else d

    if os.path.exists(settings_file):
        with open(settings_file, "r") as file:
            return _dict_to_namespace(tomli.load(file))

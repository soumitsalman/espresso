import os
import tomli
from types import SimpleNamespace
from torch import inference_mode
from sentence_transformers import SentenceTransformer
from pybeansack import Beansack, create_client

# class Embedder:
#     model = None
#     lock = None

#     def __init__(self, model_path: str, ctx_len: int): 
#         import threading
#         self.lock = threading.Lock()
#         self.model = Llama(model_path=model_path, n_ctx=ctx_len, embedding=True, verbose=False)

#     def __call__(self, text: str):
#         with self.lock:
#             vec = self.model.embed(text, truncate=True, return_count=False)
#         return vec

class AppContext:  
    db: Beansack = None
    # embedder: Embedder = None
    embedder: SentenceTransformer = None

    def __init__(self, db_kwargs: dict, embedder_kwargs: dict = None, additional_settings_file: str = None):               
        self.db = create_client(**db_kwargs)
        # if embedder_kwargs: self.embedder = Embedder(model_path=embedder_kwargs["model_name"], ctx_len=embedder_kwargs["ctx_len"]) 
        if embedder_kwargs: self.embedder = SentenceTransformer(embedder_kwargs["model_name"], tokenizer_kwargs={"truncation": True, "max_length": embedder_kwargs["ctx_len"]})
        if additional_settings_file: self.settings = load_settings(additional_settings_file)

    def embed_query(self, query: str):        
        # return self.embedder(query)  
        with inference_mode():      
            vec = self.embedder.encode_query(query, convert_to_numpy=True).tolist()
        return vec

    def close(self):
        if self.db: self.db.close()  
        if self.embedder: del self.embedder

def load_settings(settings_file: str) -> SimpleNamespace:
    """Load settings from a TOML file into a SimpleNamespace."""
    _dict_to_namespace = lambda d: SimpleNamespace(**{k: _dict_to_namespace(v) for k, v in d.items()}) if isinstance(d, dict) else d

    if os.path.exists(settings_file):
        with open(settings_file, "r") as file:
            return _dict_to_namespace(tomli.load(file))


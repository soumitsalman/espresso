import threading
from sentence_transformers import SentenceTransformer
from memoization import cached
from app.shared import env
from app.shared.utils import CACHE_SIZE, HALF_HOUR

# Initialize the model and tokenizer globally
embedder: SentenceTransformer = None
embedder_lock = threading.Lock()

@cached(max_size=CACHE_SIZE, ttl=HALF_HOUR)
def embed_query(query: str) -> list[float]:
    """Generate embeddings using the ONNX model."""
    with embedder_lock:
        vec = embedder.encode("query: "+query)
    return vec

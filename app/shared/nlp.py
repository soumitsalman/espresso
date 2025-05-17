import threading
from sentence_transformers import SentenceTransformer
from memoization import cached
from app.shared import env
from app.shared.utils import CACHE_SIZE, HALF_HOUR

# Initialize the model and tokenizer globally
embedder: SentenceTransformer = None
embedder_lock = threading.Lock()

@cached(max_size=CACHE_SIZE, ttl=HALF_HOUR)
def embed(query: str) -> list[float]:
    """Generate embeddings using the ONNX model."""
    global embedder
    with embedder_lock:
        if not embedder:
            embedder = SentenceTransformer(env.EMBEDDER_PATH, cache_folder=".models", tokenizer_kwargs={"truncation": True})
        vec = embedder.encode("query: "+query)
    return vec

from optimum.onnxruntime import ORTModelForFeatureExtraction
from transformers import AutoTokenizer
from app.shared import env
import threading

# Initialize the model and tokenizer globally
tokenizer: AutoTokenizer = None 
embedder: ORTModelForFeatureExtraction = None
embedder_lock = threading.Lock()

def embed(query: str) -> list[float]:
    """Generate embeddings using the ONNX model."""
    global embedder, tokenizer
    # with embedder_lock:
    if embedder == None:
        embedder = ORTModelForFeatureExtraction.from_pretrained(env.EMBEDDER_PATH)
        tokenizer = AutoTokenizer.from_pretrained(env.EMBEDDER_PATH)

    inputs = tokenizer(query, return_tensors="pt", padding=True, truncation=True)
    outputs = embedder(**inputs)
    # Assuming the embedding is in the first output tensor
    embedding = outputs.last_hidden_state.mean(dim=1).squeeze().tolist()
    return embedding
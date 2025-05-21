from optimum.onnxruntime import ORTModelForFeatureExtraction
from transformers import AutoTokenizer

class Embedder:
    model: ORTModelForFeatureExtraction = None
    tokenizer: AutoTokenizer = None

    def __init__(self, path: str):
        self.model = ORTModelForFeatureExtraction.from_pretrained(path)
        self.tokenizer = AutoTokenizer.from_pretrained(path)

    def embed_query(self, query: str) -> list[float]:
        inputs = self.tokenizer("query: " + query, return_tensors="pt", truncation=True)
        outputs = self.model(**inputs)
        return outputs.last_hidden_state.mean(dim=1).detach().tolist()[0]
        
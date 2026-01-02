# # local embeddings from llama.cpp
# import os
# import threading
# from llama_cpp import Llama

# class LlamaCppEmbeddings:
#     model: Llama = None
#     context_len: int = None
#     lock: threading.Lock = None

#     def __init__(self, model_path: str, context_len: int = 512):  
#         n_threads = max(1, os.cpu_count()-1)
#         self.context_len = context_len
#         self.model = Llama(model_path=model_path, n_ctx=self.context_len, n_threads_batch=n_threads, n_threads=n_threads, embedding=True, verbose=False)
#         self.lock = threading.Lock()

#     def embed_query(self, query: str):
#         with self.lock:
#             embeddings = self.model.create_embedding("query: "+query[:self.context_len<<1])
#         return embeddings['data'][0]['embedding']
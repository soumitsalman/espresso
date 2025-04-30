curl -L https://fly.io/install.sh | sh
mkdir -p .models
wget -O .models/gist-small-embeddingv-0-q8.gguf https://huggingface.co/soumitsr/GIST-small-Embedding-v0-Q8_0-GGUF/resolve/main/gist-small-embedding-v0-q8_0.gguf

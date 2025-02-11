FROM python:3.12-slim

RUN apt update && apt upgrade -y
RUN apt install -y \
    cmake \
    make \
    g++ \
    build-essential \
    wget \
    git

WORKDIR /espresso
COPY . . 

RUN pip install -r requirements.txt
RUN pip install -r app/pybeansack/requirements.txt

RUN mkdir -p /espresso/.models
RUN wget -O /espresso/.models/gist-small-embeddingv-0-q8.gguf https://huggingface.co/soumitsr/GIST-small-Embedding-v0-Q8_0-GGUF/resolve/main/gist-small-embedding-v0-q8_0.gguf
ENV EMBEDDER_PATH=/espresso/.models/gist-small-embeddingv-0-q8.gguf

EXPOSE 8080
CMD ["python3", "run.py"]

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
RUN rm -r app/connectors
RUN rm -r app/slack
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -r app/pybeansack/requirements.txt

ENV EMBEDDER_PATH=llamacpp:///espresso/.models/gist-small-embeddingv-0-q8.gguf
ENV OTEL_SERVICE_NAME=ESPRESSO-WEB
ENV MODE=web

EXPOSE 8080
CMD ["python3", "run.py"]

FROM python:3.12 AS builder

RUN apt update
RUN apt install -y \
    cmake \
    make \
    g++ \
    build-essential \
    wget \
    git

WORKDIR /build

COPY requirements.txt .
COPY app/pybeansack/requirements.txt pybeansack-requirements.txt

RUN pip install --no-cache-dir -r requirements.txt -t /python-deps
RUN pip install --no-cache-dir -r pybeansack-requirements.txt -t /python-deps

FROM python:3.12-slim

# Install minimal runtime dependencies
RUN apt update && apt install -y \
    libgomp1 \
    libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /espresso

COPY --from=builder /python-deps /usr/local/lib/python3.12/site-packages/
COPY . .
RUN rm -r app/connectors app/slack

ENV EMBEDDER_PATH=/espresso/.models/gist-small-embeddingv-0-q8.gguf
ENV OTEL_SERVICE_NAME=ESPRESSO-WEB
ENV MODE=web

EXPOSE 8080
CMD ["python3", "run.py"]

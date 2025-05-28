FROM python:3.11-slim

WORKDIR /espresso

COPY . .
RUN rm -r app/connectors
RUN rm -r app/slack
RUN pip install --no-cache-dir torch==2.6.0+cpu --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r app/pybeansack/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

ENV EMBEDDER_PATH=/espresso/models/GIST-small-Embedding-v0
ENV OTEL_SERVICE_NAME=ESPRESSO-WEB
ENV MODE=web

EXPOSE 8080
CMD ["python3", "run.py"]

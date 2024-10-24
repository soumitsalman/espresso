FROM python:3.11-slim

RUN apt update && apt install -y \
    cmake \
    make \
    g++ \
    build-essential \
    wget

WORKDIR /app 
COPY . . 
RUN pip install -r requirements.txt

EXPOSE 8080
CMD ["python3", "app.py"]
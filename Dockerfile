FROM python:3.11-slim

# RUN apt update && apt install -y \
#     cmake \
#     make \
#     g++ \
#     build-essential \
#     wget
RUN apt update && apt upgrade -y

WORKDIR /espresso
COPY . . 

RUN pip install -r requirements.txt
RUN pip install -r app/pybeansack/requirements.txt

EXPOSE 8080
CMD ["python3", "run.py"]

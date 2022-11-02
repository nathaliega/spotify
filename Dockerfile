FROM python:3.9-slim

WORKDIR /spotify
COPY requirements.txt spotify.py ./
RUN pip install -r requirements.txt

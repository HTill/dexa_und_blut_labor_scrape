FROM python:3.12-slim

WORKDIR /app

COPY web/ /app/web/
COPY data/ /app/data/

RUN ln -sf /app/data /app/web/data

WORKDIR /app/web
EXPOSE 8000

CMD ["python", "-m", "http.server", "8000"]

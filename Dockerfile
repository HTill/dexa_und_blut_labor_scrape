FROM python:3.12-slim

WORKDIR /app

COPY web/ /app/web/
RUN mkdir -p /app/web/data
COPY data/providers.json data/schema.json /app/web/data/

WORKDIR /app/web
EXPOSE 8000

CMD ["python", "-m", "http.server", "8000"]

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x ./scripts/start.sh || true

EXPOSE 8000 8001

CMD ["./scripts/start.sh"]

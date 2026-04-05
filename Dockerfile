FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Limpiar datos de ejemplo que puedan estar en el repo
RUN echo '[]' > /app/data/flota_data.json
EXPOSE 80
CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:80", "app:app"]

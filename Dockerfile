FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Crear data/ (los .json están gitignoreados, así que la carpeta no viene en el repo)
# y limpiar datos de ejemplo que puedan haber quedado.
RUN mkdir -p /app/data && echo '[]' > /app/data/flota_data.json
EXPOSE 80
CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:80", "app:app"]

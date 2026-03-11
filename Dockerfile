FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Variables de entorno con valores por defecto
ENV FLASK_SECRET_KEY=cambiar-en-produccion
ENV ADMIN_PASSWORD=admin123
ENV GUEST_PASSWORD=invitado
ENV SMTP_SERVER=smtp.gmail.com
ENV SMTP_PORT=587
ENV SMTP_EMAIL=datos@semilleroelmanantial.com
ENV SMTP_PASSWORD=""

EXPOSE 80
CMD ["gunicorn", "--bind", "0.0.0.0:80", "app:app"]

# Usamos una versión ligera de Python
FROM python:3.11-slim

# Creamos la carpeta de trabajo dentro del contenedor
WORKDIR /app

# Copiamos los requisitos e instalamos las librerías
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto del código
COPY . .

# Exponemos el puerto 80 (el estándar web)
EXPOSE 80

# Comando para iniciar la web usando Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:80", "app:app"]
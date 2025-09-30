# Dockerfile para la app Flask
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt


# Copia el archivo .env al contenedor
COPY .env .env
COPY . .

EXPOSE 5000

CMD ["python", "app.py"]

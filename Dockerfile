# Dockerfile para la app Flask
FROM python:3.9-slim

# Crear usuario no-root para seguridad
RUN useradd --create-home --shell /bin/bash app

WORKDIR /app

# Copiar e instalar dependencias
COPY hola/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación desde la carpeta hola
COPY hola/*.py ./
COPY hola/templates/ ./templates/
COPY .env .env

# Crear directorio para uploads y base de datos
RUN mkdir -p uploads && \
    chown -R app:app /app

# Cambiar a usuario no-root
USER app

EXPOSE 5000

CMD ["python", "app.py"]
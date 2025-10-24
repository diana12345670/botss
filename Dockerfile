FROM python:3.11-alpine

WORKDIR /app

# Instalar dependências de build apenas temporariamente
RUN apk add --no-cache --virtual .build-deps gcc musl-dev

# Copiar e instalar dependências Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Remover dependências de build para economizar espaço
RUN apk del .build-deps

# Copiar código do bot
COPY . /app

# Usar python otimizado (remove bytecode desnecessário)
CMD ["python", "-OO", "main.py"]

FROM python:3.11-alpine

WORKDIR /app

# Instalar dependências de build apenas temporariamente
RUN apk add --no-cache --virtual .build-deps gcc musl-dev && \
    # Limpar cache do apk
    rm -rf /var/cache/apk/*

# Copiar e instalar dependências Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt && \
    # Limpar cache do pip
    rm -rf /root/.cache/pip

# Remover dependências de build para economizar espaço
RUN apk del .build-deps

# Copiar código do bot
COPY . /app

# Remover arquivos desnecessários
RUN find . -type f -name "*.pyc" -delete && \
    find . -type d -name "__pycache__" -delete && \
    rm -rf .git .github *.md test-server.py fix-flyio.sh

# Usar python otimizado (remove bytecode e asserts)
CMD ["python", "-OO", "-u", "main.py"]

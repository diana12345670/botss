#!/bin/bash

# 🚀 Script de Deploy para Fly.io
# Uso: ./deploy.sh [novo|atualizar]

set -e

echo "🚀 Deploy no Fly.io - Bot Discord NZ Apostas"
echo ""

# Verificar se flyctl está instalado
if ! command -v fly &> /dev/null; then
    echo "❌ flyctl não está instalado!"
    echo ""
    echo "Instale com:"
    echo "curl -L https://fly.io/install.sh | sh"
    echo ""
    exit 1
fi

# Verificar se está logado
if ! fly auth whoami &> /dev/null; then
    echo "❌ Você precisa fazer login primeiro!"
    echo ""
    echo "Execute: fly auth login"
    echo ""
    exit 1
fi

# Comando: novo deploy
if [ "$1" = "novo" ]; then
    echo "📝 Criando novo app no Fly.io..."
    echo ""
    
    fly launch --no-deploy --ha=false --name botss --region gru
    
    echo ""
    echo "🔑 Configure o token do Discord:"
    echo "fly secrets set DISCORD_TOKEN=seu_token_aqui"
    echo ""
    echo "Depois execute: ./deploy.sh atualizar"
    
# Comando: atualizar
elif [ "$1" = "atualizar" ]; then
    echo "📦 Fazendo deploy..."
    echo ""
    
    fly deploy --ha=false
    
    echo ""
    echo "✅ Deploy concluído!"
    echo ""
    echo "📊 Comandos úteis:"
    echo "  fly logs -f          # Ver logs em tempo real"
    echo "  fly status           # Ver status do app"
    echo "  fly scale count 1    # Garantir 1 instância"
    echo ""
    
# Sem comando
else
    echo "Uso:"
    echo "  ./deploy.sh novo        # Criar novo app no Fly.io"
    echo "  ./deploy.sh atualizar   # Atualizar código (deploy)"
    echo ""
    echo "Exemplo primeira vez:"
    echo "  1. ./deploy.sh novo"
    echo "  2. fly secrets set DISCORD_TOKEN=seu_token"
    echo "  3. ./deploy.sh atualizar"
    echo ""
fi

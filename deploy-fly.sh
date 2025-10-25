#!/bin/bash

echo "🚀 Deploy do Bot Discord no Fly.io"
echo "===================================="
echo ""

# Adicionar flyctl ao PATH
export PATH="/home/runner/.fly/bin:$PATH"

# Verificar se está logado
echo "Verificando autenticação..."
if ! flyctl auth whoami &>/dev/null; then
    echo "❌ Você não está logado no Fly.io"
    echo "Execute: flyctl auth login"
    exit 1
fi

echo "✅ Autenticado no Fly.io"
echo ""

# Ir para o diretório do bot
cd "$(dirname "$0")"

# Verificar se o app existe
echo "Verificando se o app 'botss' existe..."
if flyctl status -a botss &>/dev/null; then
    echo "✅ App encontrado"
    
    # Fazer deploy
    echo ""
    echo "📦 Fazendo deploy..."
    flyctl deploy --ha=false --strategy immediate
    
    echo ""
    echo "🔧 Garantindo configurações corretas..."
    
    # Garantir que só há 1 máquina rodando
    flyctl scale count 1 -a botss -y
    
    # Garantir que a máquina nunca vai dormir
    flyctl machine list -a botss --json | jq -r '.[].id' | while read machine_id; do
        echo "Configurando máquina $machine_id para nunca dormir..."
        flyctl machine update $machine_id \
            --auto-stop=false \
            --auto-start=false \
            -a botss -y
    done
    
else
    echo "⚠️  App 'botss' não encontrado"
    echo ""
    echo "Criando novo app..."
    
    # Criar o app
    flyctl launch --no-deploy --ha=false --name botss --region gru
    
    # Configurar o token do Discord
    echo ""
    echo "⚠️  IMPORTANTE: Configure o token do Discord"
    echo "Execute: flyctl secrets set DISCORD_TOKEN=seu_token_aqui -a botss"
    echo ""
    read -p "Pressione ENTER depois de configurar o token..."
    
    # Fazer o primeiro deploy
    echo ""
    echo "📦 Fazendo primeiro deploy..."
    flyctl deploy --ha=false --strategy immediate
    
    # Configurar a máquina
    flyctl scale count 1 -a botss -y
    
    flyctl machine list -a botss --json | jq -r '.[].id' | while read machine_id; do
        echo "Configurando máquina $machine_id para nunca dormir..."
        flyctl machine update $machine_id \
            --auto-stop=false \
            --auto-start=false \
            -a botss -y
    done
fi

echo ""
echo "✅ Deploy concluído!"
echo ""
echo "📊 Status do bot:"
flyctl status -a botss
echo ""
echo "📋 Ver logs em tempo real:"
echo "   flyctl logs -a botss"
echo ""
echo "🌐 URL do bot (para UptimeRobot):"
echo "   https://botss.fly.dev/ping"
echo ""

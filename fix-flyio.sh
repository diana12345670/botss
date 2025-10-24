#!/bin/bash

echo "🔧 Script de correção para Fly.io - Bot Discord"
echo "================================================"
echo ""

# Verificar se fly está instalado
if ! command -v fly &> /dev/null
then
    echo "❌ flyctl não está instalado. Instale primeiro:"
    echo "   curl -L https://fly.io/install.sh | sh"
    exit 1
fi

echo "✅ flyctl encontrado"
echo ""

# Perguntar se quer destruir o app antigo
read -p "Deseja destruir o app 'botss' e criar um novo? (s/n): " resposta

if [ "$resposta" = "s" ] || [ "$resposta" = "S" ]; then
    echo ""
    echo "🗑️  Destruindo app antigo..."
    fly apps destroy botss --yes
    
    echo ""
    echo "✨ Criando novo app com configuração correta..."
    fly launch --no-deploy --ha=false --name botss --region gru
    
    echo ""
    echo "🔑 Configure o token do Discord:"
    echo "   fly secrets set DISCORD_TOKEN=seu_token_aqui"
    echo ""
    read -p "Pressione Enter após configurar o token..."
    
    echo ""
    echo "🚀 Fazendo deploy..."
    fly deploy --ha=false
else
    echo ""
    echo "📝 Tentando corrigir o app existente..."
    echo ""
    
    # Verificar máquinas rodando
    echo "Verificando máquinas..."
    fly status
    
    echo ""
    echo "🛑 Parando todas as máquinas..."
    fly scale count 0
    
    echo ""
    echo "⏳ Aguardando 5 segundos..."
    sleep 5
    
    echo ""
    echo "🚀 Fazendo deploy com configuração correta..."
    fly deploy --ha=false
    
    echo ""
    echo "📊 Iniciando 1 máquina..."
    fly scale count 1
fi

echo ""
echo "✅ Processo concluído!"
echo ""
echo "📋 Comandos úteis:"
echo "   fly logs        - Ver logs do bot"
echo "   fly status      - Ver status"
echo "   fly scale count 1 - Garantir 1 instância"
echo ""

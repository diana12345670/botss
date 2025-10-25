#!/bin/bash

echo "🔧 Corrigindo problema de múltiplas máquinas no Fly.io"
echo "======================================================"
echo ""

export PATH="/home/runner/.fly/bin:$PATH"

# Verificar autenticação
if ! flyctl auth whoami &>/dev/null; then
    echo "❌ Você precisa fazer login primeiro:"
    echo "   flyctl auth login"
    exit 1
fi

cd "$(dirname "$0")"

echo "1. Verificando quantas máquinas existem..."
num_machines=$(flyctl machine list -a botss --json 2>/dev/null | grep -c '"id"')
echo "   Máquinas encontradas: $num_machines"
echo ""

if [ "$num_machines" -gt 1 ]; then
    echo "⚠️  ATENÇÃO: Encontradas $num_machines máquinas!"
    echo "   Para um bot Discord, você precisa de APENAS 1 máquina."
    echo "   Múltiplas máquinas causam:"
    echo "   • Respostas duplicadas"
    echo "   • Conexões múltiplas ao Discord"
    echo "   • Custo dobrado"
    echo ""
    echo "2. Parando TODAS as máquinas..."
    flyctl scale count 0 -a botss -y
    sleep 5
    
    echo ""
    echo "3. Destruindo máquinas antigas..."
    flyctl machine list -a botss --json 2>/dev/null | grep -o '"id":"[^"]*"' | cut -d'"' -f4 | while read machine_id; do
        if [ ! -z "$machine_id" ]; then
            echo "   Destruindo máquina: $machine_id"
            flyctl machine destroy $machine_id -a botss --force 2>/dev/null || true
        fi
    done
    sleep 3
    
    echo ""
    echo "4. Fazendo deploy limpo (criará apenas 1 máquina)..."
    flyctl deploy --ha=false --strategy immediate -a botss
else
    echo "✅ Apenas 1 máquina encontrada (correto!)"
    echo ""
    echo "2. Fazendo deploy da versão atualizada..."
    flyctl deploy --ha=false --strategy immediate -a botss
fi

echo ""
echo "5. Garantindo que existe exatamente 1 máquina..."
flyctl scale count 1 -a botss -y
sleep 3

echo ""
echo "6. Configurando TODAS as máquinas para NUNCA dormir..."
flyctl machine list -a botss --json 2>/dev/null | grep -o '"id":"[^"]*"' | cut -d'"' -f4 | while read machine_id; do
    if [ ! -z "$machine_id" ]; then
        echo "   Configurando máquina: $machine_id"
        flyctl machine update $machine_id \
            --auto-stop=false \
            --auto-start=false \
            --yes \
            -a botss
        sleep 2
    fi
done

echo ""
echo "7. Verificando configuração anti-sleep..."
flyctl machine list -a botss

echo ""
echo "8. Verificando configuração final..."
echo ""
flyctl status -a botss
echo ""

num_final=$(flyctl machine list -a botss --json 2>/dev/null | grep -c '"id"')
echo ""
if [ "$num_final" -eq 1 ]; then
    echo "✅ PERFEITO! Apenas 1 máquina ativa."
else
    echo "⚠️  ATENÇÃO: Ainda há $num_final máquinas!"
    echo "   Execute manualmente:"
    echo "   flyctl scale count 1 -a botss -y"
fi

echo ""
echo "✅ Configuração concluída!"
echo ""
echo "📋 Resumo:"
echo "   • Máquinas ativas: 1"
echo "   • Auto-stop: DESABILITADO"
echo "   • Auto-start: DESABILITADO"
echo "   • RAM: 256MB"
echo ""
echo "🌐 URLs para UptimeRobot:"
echo "   • https://botss.fly.dev"
echo "   • https://botss.fly.dev/ping"
echo ""
echo "📊 Ver logs: flyctl logs -a botss"
echo "📋 Ver máquinas: flyctl machine list -a botss"

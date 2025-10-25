#!/bin/bash

echo "🔧 Corrigindo problema de sono do bot no Fly.io"
echo "==============================================="
echo ""

export PATH="/home/runner/.fly/bin:$PATH"

# Verificar autenticação
if ! flyctl auth whoami &>/dev/null; then
    echo "❌ Você precisa fazer login primeiro:"
    echo "   flyctl auth login"
    exit 1
fi

cd "$(dirname "$0")"

echo "1. Fazendo deploy da versão atualizada..."
flyctl deploy --ha=false --strategy immediate -a botss

echo ""
echo "2. Garantindo apenas 1 máquina..."
flyctl scale count 1 -a botss -y

echo ""
echo "3. Desabilitando auto-stop em TODAS as máquinas..."
flyctl machine list -a botss --json 2>/dev/null | grep -o '"id":"[^"]*"' | cut -d'"' -f4 | while read machine_id; do
    if [ ! -z "$machine_id" ]; then
        echo "   Configurando máquina: $machine_id"
        flyctl machine update $machine_id --auto-stop=false --auto-start=false -a botss -y 2>/dev/null
    fi
done

echo ""
echo "4. Verificando status..."
echo ""
flyctl status -a botss

echo ""
echo "✅ Pronto! O bot não deve mais dormir."
echo ""
echo "📋 Configurações aplicadas:"
echo "   • Auto-stop: DESABILITADO"
echo "   • Auto-start: DESABILITADO"
echo "   • Máquinas: 1 (sempre ativa)"
echo "   • RAM: 256MB"
echo ""
echo "🌐 URL para UptimeRobot: https://botss.fly.dev/ping"
echo ""
echo "📊 Ver logs: flyctl logs -a botss"

#!/bin/bash

echo "🔍 Verificando máquinas do bot no Fly.io"
echo "========================================"
echo ""

export PATH="/home/runner/.fly/bin:$PATH"

if ! flyctl auth whoami &>/dev/null; then
    echo "❌ Você precisa fazer login primeiro:"
    echo "   flyctl auth login"
    exit 1
fi

echo "📊 Status do app:"
flyctl status -a botss
echo ""

echo "🖥️  Lista de máquinas:"
flyctl machine list -a botss
echo ""

num_machines=$(flyctl machine list -a botss --json 2>/dev/null | grep -c '"id"')

if [ "$num_machines" -eq 1 ]; then
    echo "✅ PERFEITO! Apenas 1 máquina ativa."
    echo "   O bot está configurado corretamente."
elif [ "$num_machines" -eq 0 ]; then
    echo "⚠️  PROBLEMA: Nenhuma máquina ativa!"
    echo "   Execute: flyctl scale count 1 -a botss -y"
else
    echo "❌ PROBLEMA: $num_machines máquinas ativas!"
    echo ""
    echo "   Para um bot Discord, você deve ter APENAS 1 máquina."
    echo ""
    echo "   Problemas com múltiplas máquinas:"
    echo "   • Bot responde comandos em duplicado"
    echo "   • Conflitos na fila de apostas"
    echo "   • Custo dobrado/triplicado"
    echo ""
    echo "   SOLUÇÃO: Execute o script de correção:"
    echo "   ./fix-sleep.sh"
fi

echo ""
echo "📋 Comandos úteis:"
echo "   • Ver logs: flyctl logs -a botss"
echo "   • Forçar 1 máquina: flyctl scale count 1 -a botss -y"
echo "   • Corrigir tudo: ./fix-sleep.sh"

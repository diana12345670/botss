#!/bin/bash

# Script para corrigir problema de múltiplas máquinas no Fly.io

echo "🔍 Verificando máquinas rodando..."

cd botss

# Lista máquinas
echo ""
echo "Máquinas atuais:"
flyctl machines list

echo ""
echo "📊 Verificando status..."
flyctl status

echo ""
echo "⚙️ Escalando para exatamente 1 máquina..."
flyctl scale count 1 --yes

echo ""
echo "🔄 Aguardando 5 segundos..."
sleep 5

echo ""
echo "✅ Verificação final:"
flyctl machines list

echo ""
echo "📋 Status do app:"
flyctl status

echo ""
echo "✅ Feito! Agora só deve ter 1 máquina rodando."
echo "💡 Para fazer deploy das mudanças, rode: ./deploy-fly.sh"

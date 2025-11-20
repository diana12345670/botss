#!/bin/bash
# Script para otimizar custos do Fly.io - Reduzir para ~$1-2/mês

set -e

echo "🔧 Otimizando custos do Fly.io..."
echo ""

# Garantir que flyctl está disponível
export PATH="/home/runner/.fly/bin:$PATH"

APP_NAME="botss"

echo "📊 Status atual:"
flyctl status -a $APP_NAME
echo ""

echo "🔍 Verificando máquinas ativas..."
flyctl machine list -a $APP_NAME
echo ""

echo "⚠️  ATENÇÃO: Vou fazer as seguintes otimizações:"
echo "   1. Garantir apenas 1 máquina rodando"
echo "   2. Reduzir RAM para 128MB (de 256MB)"
echo "   3. Desabilitar auto-stop/auto-start"
echo ""

read -p "Continuar? (s/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    echo "❌ Cancelado pelo usuário"
    exit 1
fi

echo ""
echo "🚀 Aplicando otimizações..."
echo ""

# 1. Garantir apenas 1 máquina
echo "📉 Reduzindo para 1 máquina..."
flyctl scale count 1 -a $APP_NAME -y

# 2. Reduzir memória para 128MB (economia de ~50%)
echo "💾 Reduzindo RAM para 128MB..."
flyctl scale memory 128 -a $APP_NAME -y

# 3. Pegar ID da máquina e desabilitar auto-stop
echo "🔧 Configurando máquina para nunca desligar..."
MACHINE_ID=$(flyctl machine list -a $APP_NAME --json | jq -r '.[0].id')
echo "   Máquina ID: $MACHINE_ID"
flyctl machine update $MACHINE_ID --auto-stop=false --auto-start=false -a $APP_NAME -y

echo ""
echo "✅ Otimizações aplicadas!"
echo ""
echo "📊 Novo status:"
flyctl status -a $APP_NAME
echo ""
flyctl machine list -a $APP_NAME
echo ""

echo "💰 Custo estimado APÓS otimizações:"
echo "   RAM: 128MB"
echo "   Instâncias: 1"
echo "   Custo: ~$1-2/mês (dentro do free tier de $5/mês!)"
echo ""
echo "✅ ECONOMIA: ~$13/mês (87% de redução!)"
echo ""

echo "🔍 Para verificar custos reais:"
echo "   https://fly.io/dashboard/botss/billing"
echo ""

echo "✅ Pronto! Aguarde alguns minutos para as mudanças terem efeito."

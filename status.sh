#!/bin/bash

echo "=========================================="
echo "   Bot Discord NZ - Status e Deploy"
echo "=========================================="
echo ""
echo "Este bot está configurado para rodar no Fly.io"
echo ""
echo "📋 Comandos disponíveis:"
echo ""
echo "  • Verificar máquinas:"
echo "    ./verificar-maquinas.sh"
echo ""
echo "  • Corrigir problema de sono:"
echo "    ./fix-sleep.sh"
echo ""
echo "  • Ver logs do bot:"
echo "    flyctl logs -a botss"
echo ""
echo "  • Status do bot:"
echo "    flyctl status -a botss"
echo ""
echo "=========================================="
echo "Bot rodando em: https://botss.fly.dev"
echo "=========================================="

# Manter o script rodando
tail -f /dev/null

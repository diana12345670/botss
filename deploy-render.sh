#!/bin/bash

# 🚀 Script de Deploy Automático para Render
# Uso: ./deploy-render.sh

set -e

echo "🚀 Deploy Automático - Bot Discord NZ Apostas no Render"
echo ""

# Cores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Verificar se Git está configurado
if ! command -v git &> /dev/null; then
    echo -e "${RED}❌ Git não está instalado!${NC}"
    echo "Instale Git primeiro: https://git-scm.com/downloads"
    exit 1
fi

echo "📦 Preparando arquivos para deploy..."

# Verificar se já é um repositório Git
if [ ! -d ".git" ]; then
    echo -e "${YELLOW}📝 Inicializando repositório Git...${NC}"
    git init
    git add .
    git commit -m "Deploy inicial no Render"
    echo -e "${GREEN}✅ Repositório Git criado${NC}"
else
    echo -e "${GREEN}✅ Repositório Git já existe${NC}"
    
    # Verificar se há mudanças para commitar
    if ! git diff-index --quiet HEAD --; then
        echo -e "${YELLOW}📝 Commitando mudanças...${NC}"
        git add .
        git commit -m "Atualização para deploy no Render"
        echo -e "${GREEN}✅ Mudanças commitadas${NC}"
    else
        echo -e "${GREEN}✅ Não há mudanças para commitar${NC}"
    fi
fi

echo ""
echo "=========================================="
echo "📋 PRÓXIMOS PASSOS PARA DEPLOY:"
echo "=========================================="
echo ""
echo "1️⃣  CRIAR REPOSITÓRIO NO GITHUB:"
echo "   - Acesse: https://github.com/new"
echo "   - Crie um repositório (pode ser privado)"
echo "   - Copie a URL do repositório"
echo ""
echo "2️⃣  FAZER PUSH DO CÓDIGO:"
echo "   Execute os comandos abaixo (substitua a URL):"
echo ""
echo -e "${YELLOW}   git remote add origin https://github.com/SEU_USUARIO/SEU_REPO.git${NC}"
echo -e "${YELLOW}   git branch -M main${NC}"
echo -e "${YELLOW}   git push -u origin main${NC}"
echo ""
echo "3️⃣  DEPLOY NO RENDER:"
echo "   - Acesse: https://render.com"
echo "   - Clique: New + → Web Service"
echo "   - Conecte seu repositório GitHub"
echo "   - Render detectará render.yaml automaticamente ✅"
echo "   - Adicione variável de ambiente:"
echo "     • DISCORD_TOKEN: (seu token do Discord)"
echo "   - Clique: Create Web Service"
echo ""
echo "4️⃣  EVITAR QUE O BOT DURMA (IMPORTANTE!):"
echo "   - Acesse: https://uptimerobot.com"
echo "   - Add New Monitor:"
echo "     • Type: HTTP(s)"
echo "     • URL: https://SEU_APP.onrender.com/health"
echo "     • Interval: 5 minutes"
echo "   - Create Monitor"
echo ""
echo "=========================================="
echo "⚠️  ATENÇÃO - PROBLEMA DE DADOS"
echo "=========================================="
echo ""
echo "O plano GRATUITO do Render perde dados quando reinicia!"
echo ""
echo "Soluções:"
echo "  1. PostgreSQL grátis (requer código) - 100% confiável"
echo "  2. Plano pago \$7/mês - mantém tudo funcionando"
echo "  3. Aceitar perdas ocasionais de dados"
echo ""
echo "=========================================="
echo ""
echo -e "${GREEN}✅ Arquivos prontos para deploy!${NC}"
echo ""
echo "Precisa de ajuda? Veja:"
echo "  - RENDER_RAPIDO.md (guia rápido)"
echo "  - DEPLOY_RENDER.md (guia completo)"
echo ""

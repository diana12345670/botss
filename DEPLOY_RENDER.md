# 🚀 Deploy no Render - Bot Discord StormBet Apostas

## 📋 Pré-requisitos

1. Conta no Render (https://render.com) - gratuita
2. Token do bot Discord
3. Repositório Git (GitHub, GitLab ou Bitbucket)

## 🔧 Configuração Automática

### Método 1: Blueprint (Mais Fácil)

1. Faça push do código para o GitHub
2. Acesse: https://render.com
3. Clique em "New" → "Web Service"
4. Conecte seu repositório
5. O Render vai detectar o `render.yaml` automaticamente
6. Configure as variáveis de ambiente:
   - `DISCORD_TOKEN`: Seu token do Discord
7. Clique em "Create Web Service"

### Método 2: Manual

1. Acesse https://dashboard.render.com
2. Clique em "New +" → "Web Service"
3. Conecte seu repositório GitHub
4. Configure:
   - **Name**: nz-apostas-bot (ou outro nome)
   - **Region**: Oregon (US West)
   - **Branch**: main (ou sua branch)
   - **Root Directory**: ap
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py`
   - **Plan**: Free
5. Adicione variável de ambiente:
   - Key: `DISCORD_TOKEN`
   - Value: Seu token do Discord
6. Clique em "Create Web Service"

## ⚠️ IMPORTANTE: Problema do Plano Gratuito

O plano gratuito do Render tem limitações:

### ❌ Problemas:
- **Serviço dorme após 15 minutos sem requests**
- **Perde dados do arquivo JSON quando reinicia** (filesystem efêmero)
- **Filas e apostas ativas são perdidas**

### ✅ Soluções:

#### Opção 1: Manter o Bot Ativo (Grátis)
Use um serviço de ping externo para evitar que o bot durma:

**UptimeRobot** (grátis):
1. Acesse https://uptimerobot.com
2. Crie conta gratuita
3. Add New Monitor:
   - **Monitor Type**: HTTP(s)
   - **Friendly Name**: StormBet Apostas Bot
   - **URL**: `https://seu-app.onrender.com/health`
   - **Monitoring Interval**: 5 minutes
4. Save

**Outras opções**:
- Cron-job.org
- Freshping.io
- BetterUptime

#### Opção 2: Usar PostgreSQL (Recomendado)

O Render oferece PostgreSQL gratuito que **não perde dados**:

1. No Render Dashboard, crie novo PostgreSQL:
   - New + → PostgreSQL
   - Name: nz-apostas-db
   - Plan: Free
2. Adicione variável de ambiente no bot:
   - `DATABASE_URL`: (copie do PostgreSQL criado)
3. Modifique o bot para usar PostgreSQL em vez de JSON

**Nota**: Precisaria modificar o código para usar PostgreSQL. Se quiser, posso fazer isso.

#### Opção 3: Plano Pago ($7/mês)
- Sem sleep
- Filesystem persistente
- Bot sempre online
- Sem perda de dados

## 🔍 Verificação

Após deploy:

1. **Logs**: https://dashboard.render.com → seu serviço → Logs
2. **Status**: Verifique se mostra "Live" (verde)
3. **Health Check**: Acesse `https://seu-app.onrender.com/health`
4. **Discord**: Bot deve aparecer online

## 📊 Monitoramento

O bot tem endpoints para monitoramento:
- `/health` - Verifica se está rodando
- `/ping` - Ping simples
- `/` - Dashboard com informações

## 🆘 Solução de Problemas

### Bot fica offline após 15 minutos
- Configure UptimeRobot (ver Opção 1 acima)

### Perde dados das filas
- Use PostgreSQL (Opção 2) ou plano pago (Opção 3)

### Bot não conecta
- Verifique DISCORD_TOKEN nos Settings → Environment
- Veja os logs para erros

### Build falha
- Verifique se requirements.txt está correto
- Certifique-se que Python 3.11 está configurado

## 🔗 Links Úteis

- Dashboard Render: https://dashboard.render.com
- UptimeRobot: https://uptimerobot.com
- Discord Developer Portal: https://discord.com/developers/applications

## 💡 Recomendação

Para uso profissional com **zero perda de dados**:
1. ✅ Use UptimeRobot para manter ativo (grátis)
2. ✅ Migre para PostgreSQL para persistência (grátis mas requer código)
3. ✅ Ou use plano pago $7/mês (sem necessidade de mudanças)

**Melhor custo-benefício**: Render grátis + UptimeRobot + PostgreSQL = 100% grátis e confiável!

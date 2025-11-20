# ⚡ Deploy Rápido no Render

## 🚀 Passos Rápidos

### 1️⃣ Preparar Repositório
```bash
# Se ainda não tem Git configurado:
git init
git add .
git commit -m "Deploy inicial"

# Criar repositório no GitHub e fazer push
git remote add origin https://github.com/SEU_USUARIO/SEU_REPO.git
git push -u origin main
```

### 2️⃣ Deploy no Render

1. Acesse: https://render.com (crie conta se necessário)
2. Clique: **New +** → **Web Service**
3. Conecte seu repositório GitHub
4. Configuração automática (detecta `render.yaml`):
   - ✅ Build Command: `pip install -r requirements.txt`
   - ✅ Start Command: `python main.py`
   - ✅ Runtime: Python 3.11
5. Adicione variável de ambiente:
   - **DISCORD_TOKEN**: `seu_token_aqui`
6. Clique: **Create Web Service**

### 3️⃣ Evitar que o Bot Durma (IMPORTANTE!)

O plano gratuito dorme após 15 minutos. Configure ping automático:

**UptimeRobot** (Recomendado - Grátis):
1. https://uptimerobot.com → Create Account
2. Add New Monitor:
   - Type: **HTTP(s)**
   - URL: `https://SEU_APP.onrender.com/health`
   - Name: StormBet Apostas Bot
   - Interval: **5 minutes**
3. Create Monitor

✅ Pronto! Seu bot ficará sempre online!

## ⚠️ Problema de Perda de Dados

**Atenção**: O plano gratuito tem filesystem temporário. Quando o serviço reinicia, **todos os dados em `bets.json` são perdidos** (filas, apostas ativas, histórico).

### Soluções:

#### Solução 1: PostgreSQL Grátis (Recomendado)
- Dados nunca são perdidos
- Requer modificação no código
- Se quiser, posso configurar para você

#### Solução 2: Plano Pago ($7/mês)
- Filesystem persistente
- Sem modificações necessárias
- Bot sempre online sem UptimeRobot

#### Solução 3: Aceitar perda de dados
- Use apenas com UptimeRobot
- Dados são mantidos enquanto bot não reiniciar
- ⚠️ Reinicializações do Render vão apagar tudo

## 🔍 Verificar Deploy

1. **Logs**: Dashboard Render → Seu serviço → Logs
2. **Status**: Deve mostrar "Live" (verde)
3. **Bot Discord**: Deve aparecer online
4. **Health**: Abra `https://seu-app.onrender.com/health`

## 📝 Resumo

```
✅ Deploy: 5 minutos
✅ UptimeRobot: 2 minutos
⚠️ Dados persistentes: Requer PostgreSQL ou plano pago
```

**Recomendação**: Se for usar profissionalmente, invista nos $7/mês do plano pago ou configure PostgreSQL para nunca perder dados!

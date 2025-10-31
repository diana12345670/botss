# 🚀 Deploy no Fly.io - Guia Rápido

## ✅ Seu projeto está PRONTO para o Fly.io!

### 📋 O que está configurado:

- ✅ **Servidor HTTP embutido** - Health checks funcionando
- ✅ **Docker otimizado** - Imagem Alpine Linux leve (256MB RAM)
- ✅ **Sempre ativo** - Bot roda 24/7 sem dormir
- ✅ **Grátis** - Funciona no plano gratuito do Fly.io

---

## 🎯 Deploy em 3 Passos

### 1. Instalar Fly CLI (no seu computador)

**Linux/macOS:**
```bash
curl -L https://fly.io/install.sh | sh
```

**Windows (PowerShell como Administrador):**
```powershell
iwr https://fly.io/install.ps1 -useb | iex
```

### 2. Fazer Login

```bash
fly auth login
```

### 3. Deploy Automático

```bash
cd botss
./deploy.sh novo
fly secrets set DISCORD_TOKEN=seu_token_aqui
./deploy.sh atualizar
```

**Pronto! 🎉** Seu bot está online no Fly.io!

---

## 📝 Comandos Manuais (alternativa ao script)

### Primeira vez:
```bash
cd botss
fly auth login
fly launch --no-deploy --ha=false --name botss --region gru
fly secrets set DISCORD_TOKEN=seu_token_aqui
fly deploy --ha=false
fly scale count 1
fly logs
```

### Atualizar código:
```bash
cd botss
fly deploy
```

---

## 💡 Comandos Úteis

| Comando | Descrição |
|---------|-----------|
| `fly logs -f` | Ver logs em tempo real |
| `fly status` | Ver status do bot |
| `fly scale count 1` | Garantir 1 instância rodando |
| `fly dashboard` | Abrir dashboard web |
| `fly apps restart botss` | Reiniciar o bot |
| `fly scale count 0` | Pausar o bot (economizar) |
| `fly machines list` | Ver máquinas rodando |
| `fly secrets list` | Ver secrets configuradas |

---

## 💰 Custo

### Plano Gratuito Forever:
- ✅ 3 VMs compartilhadas grátis
- ✅ 256MB RAM (perfeito para seu bot)
- ✅ 160GB bandwidth/mês
- ✅ 3GB volume persistente
- ✅ **$0.00/mês** 🎉

---

## 🔍 Verificar se está funcionando

### Logs esperados:
```
✈️ Detectado ambiente Fly.io
🚀 Iniciando bot com servidor HTTP...
🌐 Servidor HTTP rodando em 0.0.0.0:8080
   Endpoints: /, /health, /ping
🤖 Conectando bot ao Discord...
Bot conectado como Nz apostas#1303
9 comandos sincronizados
📋 Registrando views persistentes...
✅ Views persistentes registradas
```

### Verificar status:
```bash
fly status
```

**Deve mostrar:** `Status: running` ✅

---

## ⚠️ Problemas Comuns

### ❌ "health check failing"
**Resolvido!** O bot agora tem servidor HTTP integrado.

### ❌ Bot respondendo duplicado
```bash
fly scale count 1
```

### ❌ Bot não conecta
```bash
fly secrets list
fly secrets set DISCORD_TOKEN=seu_novo_token
```

### ❌ Token do Discord inválido
1. Vá em https://discord.com/developers/applications
2. Selecione seu bot
3. Vá em "Bot" → "Reset Token"
4. Configure: `fly secrets set DISCORD_TOKEN=novo_token`

---

## 🎓 Estrutura do Projeto

```
botss/
├── main.py              # Bot com servidor HTTP integrado
├── models/              # Modelos de dados (Bet)
├── utils/               # Utilitários (Database)
├── data/                # Dados persistentes (bets.json)
├── Dockerfile           # Imagem Docker otimizada
├── fly.toml             # Configuração Fly.io com health checks
├── requirements.txt     # Dependências Python
└── deploy.sh            # Script automático de deploy
```

---

## 🆘 Precisa de Ajuda?

### Ver logs completos:
```bash
fly logs
```

### Entrar no container:
```bash
fly ssh console
```

### Ver uso de recursos:
```bash
fly scale show
```

### Dashboard completo:
```bash
fly dashboard
```

---

## 🎉 Pronto para Deploy!

Seu bot está 100% configurado e otimizado para o Fly.io.

Execute:
```bash
cd botss
./deploy.sh novo
```

E siga as instruções! 🚀

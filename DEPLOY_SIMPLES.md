# 🚀 Deploy no Fly.io - Guia Rápido

## ✅ O que tem de novo:

1. **Servidor HTTP de healthcheck** rodando na porta 8080
2. **3 endpoints funcionais:**
   - `/` - Status do bot
   - `/health` - Healthcheck completo
   - `/ping` - Resposta rápida "pong"
3. **Servidor inicia ANTES do bot** (evita timeout)
4. **Healthcheck TCP + HTTP** configurado

## 📋 Deploy Passo a Passo

### 1. Destruir app antigo (se necessário)
```bash
fly apps destroy botss --yes
```

### 2. Criar novo app
```bash
cd nz-apostas
fly launch --no-deploy --ha=false --name botss --region gru
```

### 3. Configurar token
```bash
fly secrets set DISCORD_TOKEN=seu_token_aqui
```

### 4. Fazer deploy
```bash
fly deploy --ha=false
```

### 5. Verificar
```bash
# Ver logs
fly logs

# Ver status
fly status

# Garantir 1 instância
fly scale count 1
```

## ✅ Logs Esperados

```
✈️ Detectado ambiente Fly.io
Iniciando bot no Fly.io com servidor HTTP...
🚀 Iniciando bot com servidor HTTP...
🌐 Servidor HTTP rodando em 0.0.0.0:8080
   Endpoints: /, /health, /ping
🤖 Conectando bot ao Discord...
Bot conectado como NZ apostas#1303
9 comandos sincronizados
```

## 🧪 Testar o Servidor HTTP

Depois do deploy, teste se o healthcheck está funcionando:

```bash
# Testar endpoint ping
curl https://botss.fly.dev/ping
# Deve retornar: pong

# Testar endpoint health
curl https://botss.fly.dev/health
# Deve retornar: Bot Status: online
#                Uptime: OK
```

## 🔍 Troubleshooting

### Bot não conecta:
```bash
fly logs
# Procure por erros de token ou conexão
```

### Healthcheck falhando:
```bash
# Verificar se porta 8080 está respondendo
fly ssh console
curl localhost:8080/ping
```

### Múltiplas instâncias:
```bash
fly scale count 1
```

## 💰 Custo

- **128MB RAM** = ~$1-2/mês
- **Dentro do free tier** do Fly.io ($5/mês grátis)

## 📝 Comandos Úteis

```bash
# Ver logs em tempo real
fly logs -f

# Parar bot (0 custo)
fly scale count 0

# Reiniciar bot
fly scale count 1

# Ver informações
fly info

# Ver uso de recursos
fly dashboard
```

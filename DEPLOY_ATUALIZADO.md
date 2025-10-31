# 🚀 Deploy Simplificado - Fly.io

## ✅ Seu projeto está 100% pronto para o Fly.io!

### O que está configurado:

1. **Servidor HTTP embutido** - O bot inicia automaticamente um servidor na porta 8080 para health checks
2. **Health checks configurados** - Fly.io verifica se o bot está online via endpoint `/ping`
3. **Otimizado para economizar** - 256MB RAM, imagem Alpine Linux leve
4. **Sempre ativo** - `auto_stop_machines = "off"` mantém o bot rodando 24/7

---

## 📝 Comandos para Deploy

### 1️⃣ Primeira vez (Criar app novo):

```bash
cd botss

# Fazer login no Fly.io
fly auth login

# Criar o app
fly launch --no-deploy --ha=false --name botss --region gru

# Configurar token do Discord
fly secrets set DISCORD_TOKEN=seu_token_aqui

# Fazer deploy
fly deploy --ha=false

# Garantir 1 instância rodando
fly scale count 1

# Ver logs
fly logs
```

### 2️⃣ Atualizar bot (após mudanças no código):

```bash
cd botss
fly deploy
```

### 3️⃣ Ver logs em tempo real:

```bash
fly logs -f
```

### 4️⃣ Ver status:

```bash
fly status
```

---

## 🎯 Logs esperados após deploy:

```
✈️ Detectado ambiente Fly.io
Iniciando bot no Fly.io com servidor HTTP...
🌐 Servidor HTTP rodando em 0.0.0.0:8080
   Endpoints: /, /health, /ping
🤖 Conectando bot ao Discord...
Bot conectado como Nz apostas#1303
9 comandos sincronizados
```

---

## 💰 Custo

**100% GRÁTIS** no plano gratuito do Fly.io:
- ✅ 3 VMs compartilhadas grátis
- ✅ 256MB RAM (seu bot usa isso)
- ✅ 160GB bandwidth/mês grátis
- ✅ Sempre ativo 24/7

---

## 🔧 Comandos Úteis

### Ver quanto está usando de recursos:
```bash
fly scale show
```

### Reiniciar o bot:
```bash
fly apps restart botss
```

### Pausar o bot (parar de consumir recursos):
```bash
fly scale count 0
```

### Reativar o bot:
```bash
fly scale count 1
```

### Deletar o app completamente:
```bash
fly apps destroy botss
```

---

## ⚠️ Troubleshooting

### Problema: "health check failing"
✅ **Resolvido!** O bot agora tem servidor HTTP embutido

### Problema: Bot respondendo em duplicado
```bash
fly scale count 1
```

### Problema: Bot não conecta ao Discord
```bash
# Verificar se o token está configurado
fly secrets list

# Reconfigurar se necessário
fly secrets set DISCORD_TOKEN=seu_token_aqui
```

---

## 📊 Monitoramento

### Dashboard web:
```bash
fly dashboard
```

### Ver histórico de deploys:
```bash
fly releases
```

### Ver máquinas rodando:
```bash
fly machines list
```

---

## ✨ Pronto!

Seu bot está configurado e otimizado. Basta executar os comandos acima! 🎉

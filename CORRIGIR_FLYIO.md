# 🔧 Deploy Atualizado no Fly.io

## ✅ NOVA VERSÃO - Servidor HTTP Incluído!

O bot agora inclui um **servidor HTTP de healthcheck** que resolve o problema de timeout!

### O que mudou:
- ✅ Servidor HTTP na porta 8080 (responde aos healthchecks)
- ✅ Bot Discord + Servidor HTTP rodam juntos
- ✅ Fly.io consegue verificar se o bot está online
- ✅ Sem mais erros de timeout!

### Deploy (Comandos Atualizados)

#### Se é a primeira vez ou quer recriar o app:

```bash
cd nz-apostas

# 1. Se já existe, destruir app antigo
fly apps destroy botss --yes  # ou nz-apostas-bot

# 2. Criar novo app
fly launch --no-deploy --ha=false --name botss --region gru

# 3. Configurar token
fly secrets set DISCORD_TOKEN=seu_token_aqui

# 4. Deploy
fly deploy --ha=false

# 5. Garantir 1 instância
fly scale count 1

# 6. Ver logs - deve mostrar servidor HTTP rodando!
fly logs
```

**Logs esperados:**
```
✈️ Detectado ambiente Fly.io
Iniciando bot no Fly.io com servidor HTTP...
🌐 Servidor HTTP rodando na porta 8080 (healthcheck)
Bot conectado como NZ apostas#1303
9 comandos sincronizados
```

#### Se quiser manter o nome "nz-apostas-bot":

```bash
# 1. Destruir app "botss" se existir
fly apps destroy botss --yes

# 2. Usar o fly.toml que já está correto
cd nz-apostas

# 3. Criar app com nome correto
fly launch --no-deploy --ha=false --name nz-apostas-bot --region gru

# 4. Configurar token
fly secrets set DISCORD_TOKEN=seu_token_aqui

# 5. Deploy
fly deploy --ha=false

# 6. Garantir 1 instância
fly scale count 1

# 7. Ver logs
fly logs
```

## 🔍 Como verificar se está correto

### 1. Verificar fly.toml (local):
```bash
cat fly.toml | grep -E "(services|http_service)"
```
**Resultado esperado:** Nada (não deve aparecer nada)

### 2. Verificar status do app:
```bash
fly status
```
**Resultado esperado:** Deve mostrar "running" ou "stopped", não "error"

### 3. Ver logs:
```bash
fly logs
```
**Resultado esperado:** Deve mostrar:
```
✈️ Detectado ambiente Fly.io
Iniciando bot no Fly.io...
Bot conectado como NZ apostas#1303
9 comandos sincronizados
```

## 📋 Checklist Final

- [ ] fly.toml NÃO tem seção `[[services]]`
- [ ] fly.toml NÃO tem seção `[http_service]`
- [ ] fly.toml TEM `kill_signal = "SIGINT"`
- [ ] fly.toml TEM `auto_rollback = false`
- [ ] Deploy foi feito com `--ha=false`
- [ ] Apenas 1 instância rodando (`fly scale count 1`)
- [ ] Token do Discord configurado (`fly secrets list`)

## 💡 Por que isso acontece?

**Bots Discord** = Conexão WebSocket permanente (não HTTP)
**Fly.io por padrão** = Espera servidor HTTP com healthcheck

**Solução** = Remover completamente healthchecks HTTP do fly.toml

## 🆘 Ainda não funcionou?

1. Copie o resultado de:
```bash
cat fly.toml
fly status
fly logs
```

2. Verifique se tem múltiplas instâncias:
```bash
fly scale show
fly scale count 1  # Forçar 1 instância
```

3. Verifique o token:
```bash
fly secrets list  # Deve mostrar DISCORD_TOKEN
```

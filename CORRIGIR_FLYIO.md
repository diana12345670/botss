# 🔧 Corrigir Erro de Timeout no Fly.io

## ❌ Erro que você está vendo:
```
Verificando https://botss.fly.dev (tentativa 3)
Último erro: tempo limite ao tentar obter seu aplicativo
```

## ✅ Solução Definitiva

O problema é que o Fly.io está tentando fazer healthcheck HTTP, mas um bot Discord não tem servidor web.

### Opção 1: Usar Script Automático (MAIS FÁCIL)

```bash
cd nz-apostas
chmod +x fix-flyio.sh
./fix-flyio.sh
```

### Opção 2: Comandos Manuais (Passo a Passo)

#### Se seu app chama "botss":

```bash
# 1. Destruir app antigo com configuração errada
fly apps destroy botss --yes

# 2. Criar novo app SEM healthchecks HTTP
fly launch --no-deploy --ha=false --name botss --region gru

# 3. IMPORTANTE: Verificar fly.toml
cat fly.toml
# Deve ter estas linhas:
# kill_signal = "SIGINT"
# kill_timeout = "5s"
# [experimental]
#   auto_rollback = false
# 
# NÃO deve ter [[services]] ou [http_service]

# 4. Se fly.toml foi gerado com [[services]], remova manualmente
# Copie o fly.toml correto deste repositório

# 5. Configurar token
fly secrets set DISCORD_TOKEN=seu_token_aqui

# 6. Deploy com flag --ha=false
fly deploy --ha=false

# 7. Garantir apenas 1 instância
fly scale count 1

# 8. Ver logs
fly logs
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

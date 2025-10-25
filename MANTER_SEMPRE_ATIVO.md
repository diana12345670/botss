# Como Manter o Bot Sempre Ativo no Fly.io

## O Problema

O Fly.io pode colocar as máquinas para dormir mesmo com o UptimeRobot fazendo ping, pois a plataforma mudou para a Machines API v2 que funciona de forma diferente.

## Solução Implementada

### 1. Configuração do fly.toml

O arquivo `fly.toml` foi atualizado com:

```toml
[http_service]
  auto_stop_machines = "off"  # NUNCA desligar
  auto_start_machines = false  # Não usar auto-start (pois nunca vai desligar)
  min_machines_running = 1     # Sempre 1 máquina rodando
```

### 2. Configuração Manual das Máquinas

Após o deploy, você DEVE configurar cada máquina individualmente:

```bash
# Listar as máquinas
flyctl machine list -a botss

# Para cada máquina, execute:
flyctl machine update MACHINE_ID --auto-stop=false --auto-start=false -a botss -y
```

Substitua `MACHINE_ID` pelo ID da máquina listada.

## Deploy Rápido (Recomendado)

Use o script automatizado que já faz tudo isso:

```bash
export PATH="/home/runner/.fly/bin:$PATH"
cd botss
./deploy-fly.sh
```

## Deploy Manual Passo a Passo

### 1. Fazer Deploy

```bash
export PATH="/home/runner/.fly/bin:$PATH"
cd botss
flyctl deploy --ha=false --strategy immediate
```

### 2. Garantir Apenas 1 Máquina

```bash
flyctl scale count 1 -a botss -y
```

### 3. Desabilitar Auto-Stop (IMPORTANTE!)

```bash
# Listar máquinas e pegar o ID
flyctl machine list -a botss

# Atualizar cada máquina
flyctl machine update MACHINE_ID --auto-stop=false --auto-start=false -a botss -y
```

### 4. Verificar Configuração

```bash
flyctl status -a botss
flyctl machine list -a botss
```

## Configurar UptimeRobot

Configure o UptimeRobot para fazer ping a cada 5 minutos:

- **URL:** https://botss.fly.dev/ping
- **Tipo:** HTTP(s)
- **Intervalo:** 5 minutos
- **Método:** GET

## Verificar se o Bot Está Ativo

```bash
# Ver logs em tempo real
flyctl logs -a botss

# Testar endpoint de ping
curl https://botss.fly.dev/ping

# Ver status das máquinas
flyctl machine list -a botss
```

## Se o Bot Ainda Estiver Dormindo

1. **Verificar se auto-stop está desabilitado:**
   ```bash
   flyctl machine list -a botss
   ```
   
   Deve mostrar algo como:
   ```
   ID            STATE   REGION  ...  AUTO_STOP
   148ed523...   started gru     ...  false
   ```

2. **Se AUTO_STOP estiver como true, corrija:**
   ```bash
   flyctl machine update MACHINE_ID --auto-stop=false -a botss -y
   ```

3. **Reiniciar a máquina:**
   ```bash
   flyctl machine restart MACHINE_ID -a botss
   ```

4. **Verificar os logs:**
   ```bash
   flyctl logs -a botss
   ```

## Custos

Com as configurações otimizadas:
- **RAM:** 256MB (aumentei um pouco para mais estabilidade)
- **CPU:** Shared (mais barato)
- **Custo estimado:** $2-3/mês
- **Crédito gratuito do Fly.io:** $5/mês

O bot fica dentro do crédito gratuito com folga.

## Comandos Úteis de Emergência

```bash
# Parar todas as máquinas
flyctl scale count 0 -a botss

# Iniciar 1 máquina
flyctl scale count 1 -a botss

# SSH na máquina (para debug)
flyctl ssh console -a botss

# Ver uso de recursos
flyctl status -a botss

# Destruir e recriar (último recurso)
flyctl apps destroy botss
./deploy-fly.sh
```

## Checklist de Deploy

- [ ] Deploy feito com `flyctl deploy --ha=false`
- [ ] Apenas 1 máquina rodando (`flyctl scale count 1`)
- [ ] Auto-stop desabilitado (`flyctl machine update ... --auto-stop=false`)
- [ ] UptimeRobot configurado para https://botss.fly.dev/ping
- [ ] Logs verificados (`flyctl logs`)
- [ ] Bot respondendo no Discord

## Dúvidas ou Problemas?

1. Verifique os logs: `flyctl logs -a botss`
2. Verifique o status: `flyctl status -a botss`
3. Teste o endpoint: `curl https://botss.fly.dev/ping`
4. Verifique as máquinas: `flyctl machine list -a botss`

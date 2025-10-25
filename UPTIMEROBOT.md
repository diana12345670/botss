# Configurar UptimeRobot - Manter Bot Ativo 24/7

## URLs Disponíveis

O bot tem **3 endpoints** para o UptimeRobot:

1. **https://botss.fly.dev** → Retorna: `OK`
2. **https://botss.fly.dev/ping** → Retorna: `pong`
3. **https://botss.fly.dev/health** → Status detalhado

## Configuração Recomendada

Configure **2 monitores** no UptimeRobot para redundância:

### Monitor 1: URL Raiz
- **URL:** `https://botss.fly.dev`
- **Tipo:** HTTP(s)
- **Intervalo:** 5 minutos
- **Palavra-chave:** `OK`

### Monitor 2: Endpoint Ping
- **URL:** `https://botss.fly.dev/ping`
- **Tipo:** HTTP(s)
- **Intervalo:** 5 minutos
- **Palavra-chave:** `pong`

## Passo a Passo

1. Acesse https://uptimerobot.com
2. Clique em **"+ Add New Monitor"**
3. Configure conforme acima
4. Repita para o segundo monitor

## Testar Endpoints

```bash
curl https://botss.fly.dev
# Retorna: OK

curl https://botss.fly.dev/ping
# Retorna: pong
```

Ambos funcionam perfeitamente para o UptimeRobot! 🚀

# Deploy no Fly.io - Bot Discord NZ Apostas

## Pré-requisitos
1. Conta no Fly.io (https://fly.io)
2. flyctl CLI instalado

## Instalação do flyctl

### Linux/macOS
```bash
curl -L https://fly.io/install.sh | sh
```

### Windows (PowerShell)
```powershell
iwr https://fly.io/install.ps1 -useb | iex
```

## Passo a passo para deploy

### 1. Fazer login no Fly.io
```bash
fly auth login
```

### 2. Criar o app (primeira vez)
```bash
cd nz-apostas
fly launch --no-deploy --ha=false
```

**IMPORTANTE:** 
- Quando perguntar sobre PostgreSQL, digite **N** (o bot usa JSON local)
- Quando perguntar sobre IPv4 dedicado, digite **N** (bot Discord não precisa)
- Quando perguntar sobre deploy imediato, digite **N**
- Após o comando, **verifique se o fly.toml NÃO tem seção [[services]] ou [http_service]]** - se tiver, remova!

### 3. Configurar o token do Discord
```bash
fly secrets set DISCORD_TOKEN=seu_token_aqui
```

### 4. Fazer o deploy
```bash
fly deploy --ha=false
```

**IMPORTANTE:** Use sempre `--ha=false` para economizar recursos e evitar múltiplas instâncias

### 5. Ver os logs
```bash
fly logs
```

### 6. Verificar status
```bash
fly status
```

## Comandos úteis

### Ver logs em tempo real
```bash
fly logs -f
```

### Garantir que só há 1 instância rodando
```bash
fly scale count 1
```

### Ver informações do app
```bash
fly info
```

### SSH no servidor
```bash
fly ssh console
```

### Parar o bot
```bash
fly scale count 0
```

### Reiniciar o bot
```bash
fly scale count 1
```

### Deletar o app
```bash
fly apps destroy nz-apostas-bot
```

## Atualizar o bot

Sempre que fizer mudanças no código:
```bash
fly deploy
```

## Custo e Otimização

### Recursos Otimizados
Este bot foi configurado para ser **super econômico**:
- **RAM:** 128MB (suficiente para um bot Discord)
- **Imagem:** Python Alpine (muito mais leve que Slim)
- **Logs:** Apenas erros (economiza processamento)
- **Intents:** Somente o necessário (economiza RAM e bandwidth)

### Custo Mensal
- Fly.io oferece $5 de crédito gratuito por mês
- Este bot otimizado consome aproximadamente **$1-2/mês** 
- O bot roda 24/7

### Dicas para economizar ainda mais
```bash
# Ver quanto está consumindo
fly scale show

# Se o bot estiver usando muita RAM, monitore
fly dashboard

# Parar o bot quando não estiver usando (0 custo)
fly scale count 0

# Reiniciar quando precisar
fly scale count 1
```

## Persistência de dados

Os dados das apostas são salvos em `/app/data/bets.json` dentro do container.
**ATENÇÃO:** Se o container for destruído, os dados serão perdidos.

Para persistência permanente, recomenda-se:
1. Usar Fly.io Volumes (armazenamento persistente)
2. Migrar para PostgreSQL

## Troubleshooting

### ❌ Erro "timeout trying to get your app" ou "health check failing"

**Causa:** Fly.io está tentando fazer healthcheck HTTP, mas bot Discord não tem servidor web.

**Solução Rápida (RECOMENDADO):**
```bash
cd nz-apostas
./fix-flyio.sh
```

**Solução Manual - Opção 1 (Criar app novo):**
```bash
# 1. Destruir app antigo
fly apps destroy botss --yes

# 2. Criar novo app
fly launch --no-deploy --ha=false --name botss --region gru

# 3. Verificar que fly.toml NÃO tem [[services]] ou [http_service]
cat fly.toml

# 4. Configurar token
fly secrets set DISCORD_TOKEN=seu_token_aqui

# 5. Deploy
fly deploy --ha=false

# 6. Garantir 1 instância
fly scale count 1
```

**Solução Manual - Opção 2 (Corrigir app existente):**
```bash
# 1. Parar todas as máquinas
fly scale count 0

# 2. Verificar que fly.toml está correto (sem [[services]])
cat fly.toml

# 3. Deploy novamente
fly deploy --ha=false

# 4. Iniciar 1 máquina
fly scale count 1

# 5. Ver logs
fly logs
```

**Verificar se fly.toml está correto:**
```bash
# Deve mostrar "0" (não deve ter [[services]])
grep -c "services" fly.toml
```

### Bot está respondendo em duplicado
```bash
fly scale count 1
```

### Ver configuração atual
```bash
fly scale show
```

### Bot não está iniciando
```bash
fly logs
```
Verifique se o DISCORD_TOKEN está configurado corretamente

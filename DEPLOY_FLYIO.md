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
fly launch --no-deploy
```

**IMPORTANTE:** 
- Quando perguntar sobre PostgreSQL, digite **N** (o bot usa JSON local)
- Quando perguntar sobre deploy imediato, digite **N**

### 3. Configurar o token do Discord
```bash
fly secrets set DISCORD_TOKEN=seu_token_aqui
```

### 4. Fazer o deploy
```bash
fly deploy
```

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

## Custo

- Fly.io oferece $5 de crédito gratuito por mês
- Um bot Discord com 256MB de RAM consome aproximadamente $2-3/mês
- O bot roda 24/7

## Persistência de dados

Os dados das apostas são salvos em `/app/data/bets.json` dentro do container.
**ATENÇÃO:** Se o container for destruído, os dados serão perdidos.

Para persistência permanente, recomenda-se:
1. Usar Fly.io Volumes (armazenamento persistente)
2. Migrar para PostgreSQL

## Troubleshooting

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

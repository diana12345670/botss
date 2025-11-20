
# Deploy do Bot StormBet Apostas no Railway

Este guia explica como fazer o deploy do bot Discord no Railway.

## ✨ Detecção Automática de Ambiente

O bot **detecta automaticamente** quando está rodando no Railway através das variáveis de ambiente `RAILWAY_ENVIRONMENT` ou `RAILWAY_STATIC_URL`. Você não precisa fazer nenhuma configuração adicional!

Quando detectado no Railway, o bot:
- 🚂 Exibe mensagem "Detectado ambiente Railway"
- 📁 Usa o diretório `/app/data` para dados persistentes
- 🔍 Mostra traceback completo de erros
- ⚙️ Usa configurações de logging otimizadas

## Pré-requisitos

1. Conta no [Railway](https://railway.app/)
2. Token do bot Discord configurado
3. Código do bot no GitHub (ou upload direto)

## Passo a Passo

### 1. Preparar o Repositório

Se você ainda não tem o código no GitHub:

1. Crie um novo repositório no GitHub
2. Faça upload de todos os arquivos da pasta `nz-apostas`
3. Certifique-se de que os arquivos `railway.json`, `Procfile`, `runtime.txt` e `requirements.txt` estão incluídos

### 2. Criar Projeto no Railway

1. Acesse [railway.app](https://railway.app/)
2. Faça login com sua conta GitHub
3. Clique em **"New Project"**
4. Selecione **"Deploy from GitHub repo"**
5. Escolha o repositório com o código do bot
6. Railway detectará automaticamente que é um projeto Python

### 3. Configurar Variáveis de Ambiente

1. No dashboard do projeto, vá em **"Variables"**
2. Adicione a seguinte variável:
   - `TOKEN`: Cole o token do seu bot Discord

**IMPORTANTE:** 
- Nunca compartilhe ou commite o token do bot no GitHub!
- O Railway define automaticamente `RAILWAY_ENVIRONMENT` e `RAILWAY_STATIC_URL`

### 4. Configurar Deploy

Railway detectará automaticamente o `railway.json` e `Procfile`. Se necessário:

1. Vá em **"Settings"**
2. Em **"Deploy"**, confirme que:
   - **Start Command**: `python main.py`
   - **Build Command**: (deixe em branco, Railway instalará dependências automaticamente)

### 5. Deploy

1. Railway iniciará o deploy automaticamente
2. Aguarde a instalação das dependências
3. O bot iniciará quando o deploy estiver completo
4. Verifique os logs em **"Deployments"** → **"View Logs"**

### 6. Verificar Status

Para confirmar que o bot está online:

1. Verifique os logs do Railway
2. Procure por mensagens como:
   ```
   🚂 Detectado ambiente Railway
   Iniciando bot no Railway...
   Bot conectado como NZ apostas#1303
   Nome: NZ apostas
   ID: 1431031103401103474
   8 comandos sincronizados
   ```
3. Teste um comando no Discord

## Troubleshooting

### Bot não conecta

- Verifique se o `TOKEN` está configurado corretamente nas variáveis de ambiente
- Confirme que o token é válido no [Discord Developer Portal](https://discord.com/developers/applications)
- Verifique os logs completos no Railway (o bot mostra traceback detalhado)

### Erros de dependências

- Verifique se o arquivo `requirements.txt` está presente
- Confirme que `discord.py==2.6.4` está listado

### Bot desconecta frequentemente

- Railway oferece planos gratuitos com limitações
- Considere fazer upgrade para um plano pago para melhor estabilidade

### Logs não aparecem

- Vá em **"Deployments"** → clique no deploy ativo → **"View Logs"**
- Os logs podem levar alguns segundos para aparecer
- Procure pela mensagem "🚂 Detectado ambiente Railway"

### Banco de dados não persiste

- Configure um Volume no Railway (veja seção abaixo)
- Monte o volume em `/app/data`

## Estrutura de Arquivos Necessária

```
nz-apostas/
├── main.py                 # Código principal do bot (com detecção Railway)
├── models/
│   ├── __init__.py
│   └── bet.py
├── utils/
│   ├── __init__.py
│   └── database.py        # Sistema de dados (com suporte Railway)
├── data/
│   └── bets.json          # Será criado automaticamente
├── requirements.txt       # Dependências Python
├── runtime.txt            # Versão do Python
├── Procfile              # Comando de start
├── railway.json          # Configuração Railway
└── README.md
```

## Persistência de Dados

**ATENÇÃO:** O Railway não mantém arquivos entre deploys por padrão. O arquivo `data/bets.json` será perdido em cada redeploy.

### Soluções:

1. **Railway Volumes** (Recomendado):
   ```bash
   # O bot detectará automaticamente o volume se montado em /app/data
   ```
   - No Railway, vá em **"Settings"** → **"Volumes"**
   - Crie um novo volume
   - Monte-o em `/app/data`
   - O bot usará automaticamente este diretório

2. **Banco de Dados Externo**:
   - Use PostgreSQL, MongoDB ou outro banco
   - Railway oferece add-ons de banco de dados

3. **Armazenamento em Nuvem**:
   - Use S3, Google Cloud Storage, etc.
   - Sincronize o `bets.json` periodicamente

## Monitoramento

- **Logs**: Railway → Deployments → View Logs
  - Procure por "🚂 Detectado ambiente Railway"
  - Erros mostram traceback completo
- **Métricas**: Railway → Observability
- **Alertas**: Configure notificações no Discord para erros

## Redeploy Automático

Railway faz redeploy automático quando você:
- Faz push para o branch principal do GitHub
- Modifica variáveis de ambiente
- Clica em "Redeploy" manualmente

## Custos

- **Plano Gratuito**: 
  - $5 em créditos por mês
  - 500 horas de execução
  - Ideal para testes

- **Plano Hobby**: 
  - $5/mês + uso
  - Sem limite de horas
  - Recomendado para produção

## Suporte

- [Documentação Railway](https://docs.railway.app/)
- [Discord da Railway](https://discord.gg/railway)
- [Status do Railway](https://status.railway.app/)

## Diferenças vs Replit

| Recurso | Replit | Railway |
|---------|--------|---------|
| Deploy Automático | ✅ | ✅ |
| Detecção de Ambiente | ✅ | ✅ Automática |
| Persistência | ✅ Built-in | ⚠️ Requer Volume |
| Logs | ✅ | ✅ Mais detalhados |
| Custo Gratuito | Limitado | $5 créditos/mês |
| Uptime | Bom | Excelente |
| Facilidade | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

## Próximos Passos

1. ✅ Deploy inicial (detecção automática funciona!)
2. Configure um volume persistente para `/app/data`
3. Adicione monitoramento de erros
4. Configure backup automático dos dados
5. Implemente health checks

---

**Nota**: Este bot está atualmente deployado no Replit. Esta é apenas uma cópia de backup para Railway que detecta automaticamente o ambiente.

# Como Rodar Múltiplos Bots no Render

## 🎯 Suporte para 2 Tokens

Este bot agora **suporta rodar 2 tokens no mesmo processo**!

Para rodar 2 bots, você tem duas opções:

### ✅ Opção 1: 2 Tokens no Mesmo Deployment (NOVO!)

Agora você pode rodar 2 bots Discord no mesmo Web Service:

1. **Configure as variáveis de ambiente:**
   - `TOKEN_1` = Token do primeiro bot
   - `TOKEN_2` = Token do segundo bot
   - `DATABASE_URL` = URL do PostgreSQL (opcional, mas recomendado)

2. **Deploy!**
   - O bot detecta automaticamente os 2 tokens
   - Ambos rodam em paralelo no mesmo processo
   - Compartilham o mesmo database

**Vantagens:**
- ✅ Mais econômico (1 Web Service em vez de 2)
- ✅ Compartilham banco de dados automaticamente
- ✅ Fácil de configurar

**Desvantagens:**
- ⚠️ Se o processo cair, ambos os bots caem juntos
- ⚠️ Limitado a 2 tokens apenas

### ✅ Opção 2: Múltiplos Web Services (Para 3+ bots)

Para rodar 3 ou mais bots, use múltiplos Web Services:

### 📋 Passo a Passo

1. **Criar PostgreSQL** (apenas uma vez)
   - No Render Dashboard, crie um PostgreSQL Database
   - Copie a URL de conexão (`DATABASE_URL`)

2. **Criar Web Service para Bot #1**
   - Crie um novo Web Service no Render
   - Conecte ao seu repositório
   - Configure as variáveis de ambiente:
     - `TOKEN` ou `DISCORD_TOKEN` = Token do Bot 1
     - `DATABASE_URL` = URL do PostgreSQL criado acima
   - Deploy!

3. **Criar Web Service para Bot #2**
   - Crie OUTRO Web Service no Render
   - Conecte ao MESMO repositório
   - Configure as variáveis de ambiente:
     - `TOKEN` ou `DISCORD_TOKEN` = Token do Bot 2
     - `DATABASE_URL` = MESMA URL do PostgreSQL
   - Deploy!

4. **Repetir para Bot #3, #4, #5...**
   - Cada bot = 1 Web Service
   - Todos compartilham o mesmo `DATABASE_URL`

### ✅ Vantagens

- ✅ **Isolamento**: Cada bot roda em seu próprio processo
- ✅ **Estabilidade**: Se um bot cai, os outros continuam funcionando
- ✅ **Fácil de gerenciar**: Cada bot tem seu próprio dashboard
- ✅ **Compartilham dados**: Todos usam o mesmo banco de dados PostgreSQL
- ✅ **Escalabilidade**: Adicione mais bots criando novos serviços

### 📊 Dados Compartilhados

Como todos os bots usam o mesmo `DATABASE_URL`, eles compartilham:
- ✅ Configurações de servidores (`/setup`)
- ✅ Assinaturas de servidores
- ✅ Histórico de apostas
- ⚠️ Filas são SEPARADAS (cada bot tem suas próprias filas)

## ❌ O Que NÃO Fazer

**❌ NÃO tente rodar múltiplos bots no mesmo Web Service**
- O código atual não suporta múltiplos tokens no mesmo processo
- Isso causaria conflitos e bugs difíceis de rastrear

## 🔍 Verificação

Para confirmar que está funcionando:
1. Veja os logs de cada Web Service
2. Você deve ver: `✅ BOT CONECTADO AO DISCORD!`
3. Cada bot aparecerá online no Discord

## 💰 Custos no Render

- **PostgreSQL**: Gratuito (512MB)
- **Cada Web Service**: ~$7/mês (ou gratuito com limitações)
- **5 bots = 5 Web Services** = ~$35/mês
- **Dica**: Use o plano gratuito para testar primeiro!

## 🆘 Problemas Comuns

**Bot não inicia:**
- Verifique se `TOKEN` ou `DISCORD_TOKEN` está configurado
- Verifique se o token está correto

**Dados não são salvos:**
- Verifique se `DATABASE_URL` está configurado
- Verifique se o PostgreSQL está rodando

**Bots compartilham filas incorretamente:**
- Isso é esperado! Cada bot tem suas próprias filas
- Se quiser compartilhar filas, use apenas 1 bot

## 📝 Notas sobre Tokens

**Prioridade de detecção:**
1. Se existe `TOKEN` ou `DISCORD_TOKEN`: usa apenas esse (1 bot)
2. Se existe `TOKEN_1` e `TOKEN_2`: roda 2 bots em paralelo
3. Se existe apenas `TOKEN_1`: usa esse (1 bot)

**Limitações:**
- ✅ Suporte para **até 2 tokens** no mesmo processo
- ❌ Não suporta `TOKEN_3`, `TOKEN_4`, `TOKEN_5` (para isso use múltiplos Web Services)

## 🔍 Como Verificar se Está Funcionando

**Com 1 token:**
```
🤖 Iniciando bot Discord (token único)...
✅ BOT CONECTADO AO DISCORD!
```

**Com 2 tokens:**
```
🤖 Detectados 2 tokens - iniciando 2 bots em paralelo...
📋 Copiando comandos para segundo bot...
🤖 Bot #1: Conectando ao Discord...
🤖 Bot #2: Conectando ao Discord...
✅ BOT CONECTADO AO DISCORD! (aparece 2x)
```

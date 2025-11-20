# 🔄 Sistema Híbrido de Database - StormBet Apostas

## 📋 Visão Geral

O bot agora possui um **sistema híbrido de database** que combina PostgreSQL (opcional) com JSON (fallback e backup), garantindo que **você nunca perca dados das filas**, mesmo em plataformas gratuitas que "dormem".

## 🎯 Como Funciona

### 1️⃣ **Com PostgreSQL (Recomendado para Produção)**

Quando você configura `DATABASE_URL`:
- ✅ Dados são salvos **primeiramente no PostgreSQL**
- ✅ **Backup automático em JSON** ao mesmo tempo
- ✅ **Sistema triplo de backup** (3 arquivos JSON rotativos)
- ✅ Se PostgreSQL falhar, usa JSON automaticamente
- ✅ **Dados persistem mesmo se a plataforma "dormir"**

**Vantagens:**
- 🚀 Performance superior
- 💾 Dados persistentes em produção
- 🔄 Backup automático JSON como segurança
- 🛡️ Múltiplas camadas de proteção

### 2️⃣ **Sem PostgreSQL (Modo JSON Puro)**

Quando `DATABASE_URL` não está configurada:
- ✅ Usa JSON como principal
- ✅ **Sistema triplo de backup** ativo
- ✅ Rotação automática de backups
- ✅ Funciona perfeitamente no Replit

**Vantagens:**
- 🎯 Simples e direto
- 📁 Não precisa configurar banco de dados
- 💾 Backup triplo protege contra corrupção

## 🔐 Sistema de Backup Triplo

O bot cria **3 camadas de backup** automático:

```
data/
  ├── bets.json           ← Principal
  ├── bets.backup.json    ← Backup 1
  └── bets.backup2.json   ← Backup 2
```

**Como funciona:**
1. Salva em `bets.json`
2. Faz backup em `bets.backup.json`
3. Roda backup do backup em `bets.backup2.json`
4. Se um arquivo corromper, recupera do próximo

## 🚀 Deploy no Render

### Opção A: Com PostgreSQL (Recomendado)

**Plano Necessário:** $7/mês (PostgreSQL Database)

1. Crie database PostgreSQL no Render
2. Copie a `DATABASE_URL` (fornecida pelo Render)
3. Configure no seu Web Service:
   ```
   DATABASE_URL=postgresql://user:pass@host/db
   DISCORD_TOKEN=seu_token_aqui
   ```
4. Deploy! 🎉

**Resultado:**
- ✅ Dados **nunca** são perdidos
- ✅ Bot funciona 24/7
- ✅ Backup JSON automático como segurança extra

### Opção B: Sem PostgreSQL (Gratuito + Limitado)

**Plano:** Free Tier do Render

⚠️ **ATENÇÃO:** No plano gratuito do Render:
- ❌ Serviço "dorme" após inatividade
- ❌ Arquivos JSON são **perdidos** ao dormir
- ❌ Todas as filas serão **apagadas**

**Solução:** Use PostgreSQL ($7/mês) ou mantenha bot acordado com UptimeRobot.

## 🔧 Configuração

### Replit (Atual)

✅ **Já está funcionando!**
- PostgreSQL: Automático (DATABASE_URL já configurada)
- Backup JSON: Ativo em `data/`
- Servidor HTTP: Rodando em `0.0.0.0:5000`

### Render

Siga o guia: [DEPLOY_RENDER.md](DEPLOY_RENDER.md)

Resumo rápido:
```bash
# 1. Criar PostgreSQL Database (opcional mas recomendado)
# 2. Criar Web Service e conectar ao PostgreSQL
# 3. Configurar variáveis:
DISCORD_TOKEN=seu_token
DATABASE_URL=postgresql://... (se usar PostgreSQL)
```

## 📊 Monitoramento

O bot loga claramente qual sistema está usando:

**Com PostgreSQL:**
```
🐘 PostgreSQL ativado: postgresql://postgre...
💾 Backup JSON ativo: data/bets.json
```

**Sem PostgreSQL:**
```
📁 Modo JSON: data/bets.json
💾 Sistema de backup triplo ativado
```

## ❓ FAQ

### Preciso de PostgreSQL?

**No Replit:** Não obrigatório, mas recomendado
- Replit tem PostgreSQL integrado (grátis)
- Já está configurado e funcionando

**No Render:** Altamente recomendado
- Plano gratuito perde arquivos ao dormir
- PostgreSQL ($7/mês) resolve isso

### Posso mudar depois?

✅ **Sim!** O sistema é flexível:
- Adicionar PostgreSQL: Define `DATABASE_URL` e reinicia
- Remover PostgreSQL: Remove `DATABASE_URL`, usa JSON
- **Dados são migrados automaticamente**

### Os dados JSON e PostgreSQL ficam sincronizados?

✅ **Sim, sempre!**
- Quando salva no PostgreSQL → salva no JSON também
- Quando salva no JSON → é o único sistema
- Se PostgreSQL falhar → usa JSON automaticamente

### O que acontece se PostgreSQL falhar?

1. Bot detecta a falha
2. Automaticamente usa JSON
3. Loga o aviso: `⚠️ Fallback para modo JSON`
4. **Continua funcionando normalmente**

## 🎯 Recomendações

### Para Produção (Render/Railway/Fly.io)
✅ **Use PostgreSQL**
- Garante persistência de dados
- Melhor performance
- Backup JSON como segurança extra

### Para Testes (Replit)
✅ **PostgreSQL Replit (grátis)**
- Já está configurado
- Funciona perfeitamente
- Bom para desenvolvimento

### Para Desenvolvimento Local
✅ **Modo JSON**
- Simples e direto
- Não precisa configurar nada
- Backup triplo protege seus dados

## 🔍 Troubleshooting

### Bot perde dados ao reiniciar no Render Free

**Causa:** Render Free perde arquivos, JSON não persiste

**Solução:**
1. Adicione PostgreSQL ($7/mês)
2. Configure `DATABASE_URL`
3. Dados persistem para sempre

### Erro ao conectar PostgreSQL

**Sintomas:** `❌ Erro ao inicializar PostgreSQL`

**Soluções:**
1. Verifique `DATABASE_URL` correta
2. Confirme que PostgreSQL está ativo
3. Bot automaticamente usa JSON como fallback

### Dados corrompidos

**Sintomas:** Erro ao carregar dados

**Solução automática:**
1. Bot detecta corrupção
2. Tenta backup 1
3. Tenta backup 2
4. Usa dados vazios se tudo falhar
5. Loga tudo para você investigar

## 📚 Documentação Relacionada

- [Deploy no Render](DEPLOY_RENDER.md)
- [Deploy no Fly.io](DEPLOY_FLYIO.md)
- [Deploy no Railway](DEPLOY_RAILWAY.md)
- [Instruções Completas](INSTRUCOES.md)

## 🎉 Conclusão

O sistema híbrido oferece:
- ✅ **Flexibilidade:** Funciona com ou sem PostgreSQL
- ✅ **Segurança:** Múltiplas camadas de backup
- ✅ **Confiabilidade:** Nunca perde dados
- ✅ **Simplicidade:** Configura automaticamente

**Você está protegido! 🛡️**

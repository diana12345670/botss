# Correções Aplicadas - 15/11/2025

## Problemas Corrigidos

### 1. ✅ Comandos Não Aparecendo
**Problema**: Logs mostravam "✅ 0 comandos sincronizados globalmente"  
**Causa**: `bot.tree.clear_commands()` estava apagando todos os comandos antes de sincronizar  
**Solução**: Removida a linha que apagava os comandos. Agora sincroniza os comandos definidos com decoradores `@bot.tree.command`

### 2. ✅ Bot Saindo de Servidores Existentes
**Problema**: Bot estava saindo de todos os servidores sem assinatura  
**Causa**: Lógica antiga verificava assinatura e saía imediatamente  
**Solução**: Implementada auto-assinatura de 10 dias para todos os servidores

## Mudanças Implementadas

### Arquivo: `fly.toml`
- ✅ `max_machines_running = 1` - Garante apenas 1 VM rodando
- ✅ Health check melhorado (60s intervalo, 20s timeout)
- ✅ Grace period aumentado para 30s

### Arquivo: `main.py`

#### 1. Sincronização de Comandos (linha ~1148)
**Antes:**
```python
bot.tree.clear_commands(guild=None)  # ❌ Apagava tudo
synced_global = await bot.tree.sync(guild=None)
```

**Depois:**
```python
synced_global = await bot.tree.sync(guild=None)  # ✅ Só sincroniza
```

#### 2. Entrada em Novo Servidor (`on_guild_join`)
**Antes:**
```python
if not await ensure_guild_authorized(guild):
    log(f"❌ Servidor {guild.name} não está autorizado, saindo...")
    # Saía do servidor
```

**Depois:**
```python
# Servidor auto-autorizado = permanente
if guild.id == AUTO_AUTHORIZED_GUILD_ID:
    db.create_subscription(guild.id, None)
    return

# Outros servidores = 10 dias grátis
if not db.is_subscription_active(guild.id):
    duration_days = 10
    duration_seconds = duration_days * 86400
    db.create_subscription(guild.id, duration_seconds)
    # Envia mensagem de boas-vindas com data de expiração
```

#### 3. Verificação Inicial de Servidores (`on_ready`)
**Antes:**
```python
for guild in bot.guilds:
    if not db.is_subscription_active(guild.id):
        await ensure_guild_authorized(guild)  # Saía do servidor
```

**Depois:**
```python
for guild in bot.guilds:
    if not db.is_subscription_active(guild.id):
        # Cria 10 dias automaticamente
        db.create_subscription(guild.id, 10 * 86400)
        # Envia notificação
```

## Como Aplicar

```bash
cd botss
flyctl deploy
```

Ou usando os scripts:
```bash
cd botss
./deploy-fly.sh
```

## Verificação Pós-Deploy

### 1. Verificar Comandos
```bash
flyctl logs
```

Deve aparecer:
```
✅ 15 comandos sincronizados globalmente (DM incluída)
  - /mostrar-fila
  - /setup
  - /ajuda
  - /confirmar-pagamento
  - ...
```

### 2. Verificar Servidores
Os servidores existentes devem receber:
- ✅ 10 dias de assinatura automática
- ✅ Mensagem de notificação no canal do servidor
- ❌ NÃO devem ser removidos

### 3. Novos Servidores
Quando adicionar o bot a um novo servidor:
- ✅ Recebe 10 dias automaticamente
- ✅ Mensagem de boas-vindas com instruções
- ✅ Data de expiração clara

## Comportamento Esperado

### Servidor Auto-Autorizado (ID: 1438184380395687978)
- Assinatura: **Permanente** (nunca expira)
- Não recebe mensagens de aviso

### Novos Servidores
- Assinatura: **10 dias grátis**
- Mensagem de boas-vindas com:
  - Período de teste (10 dias)
  - Data de expiração
  - Instruções para começar (`/setup`)
  - Informações de contato para renovação

### Servidores Existentes
- Assinatura: **10 dias grátis** (a partir do deploy)
- Mensagem de notificação explicando:
  - Sistema de assinatura foi implementado
  - Ganhou 10 dias como cortesia
  - Informações de contato para renovação

### Após Expiração
- Bot sai do servidor automaticamente
- Envia mensagem de aviso antes de sair
- Administrador pode solicitar renovação

## Comandos Disponíveis

Todos os 15 comandos estão ativos:
1. `/mostrar-fila` - Criar fila de apostas
2. `/confirmar-pagamento` - Confirmar pagamento
3. `/finalizar-aposta` - Finalizar aposta (mediador)
4. `/cancelar-aposta` - Cancelar aposta (mediador)
5. `/historico` - Ver histórico
6. `/minhas-apostas` - Ver apostas ativas
7. `/sair-todas-filas` - Sair de filas
8. `/desbugar-filas` - Limpar filas (admin)
9. `/setup` - Configurar servidor (admin)
10. `/ajuda` - Ver ajuda
11. `/servidores` - Listar servidores (criador)
12. `/criar-assinatura` - Criar assinatura (criador)
13. `/assinatura-permanente` - Assinatura permanente (criador)
14. `/sair` - Sair de servidor (criador)
15. `/autorizar-servidor` - Autorizar servidor (criador)
16. `/aviso-do-dev` - Enviar aviso (criador)

## Notas Importantes

- **Cache do Discord**: Comandos podem demorar até 1 hora para aparecer
- **Força Atualização**: Use Ctrl+R no Discord para limpar cache
- **Apenas 1 VM**: Configuração garante que só 1 instância roda
- **Sem Invalidação**: Problema de "sessão invalidada" está resolvido

## Monitoramento

```bash
# Ver logs em tempo real
flyctl logs

# Ver status
flyctl status

# Ver máquinas rodando (deve ser apenas 1)
flyctl machines list

# Ver health check
curl https://botss.fly.dev/health
```

Deve retornar:
```
Bot Status: online
Guilds: X
Uptime: OK
```

# Correção dos Problemas de Fila e Comandos

## Problemas Identificados

Analisando os logs do Fly.io, foram identificados 2 problemas principais:

### 1. Múltiplas Instâncias Rodando
- **Sintoma**: Sessões sendo invalidadas ("A sessão Shard ID None foi invalidada")
- **Causa**: Duas VMs diferentes rodando ao mesmo tempo (e7847924ce3908 e 4d8946d9ced028)
- **Consequência**: Ambas tentam conectar ao Discord com o mesmo token, causando conflito

### 2. Comandos Não Encontrados
- **Sintoma**: Erros "CommandNotFound" para vários comandos (setup, ajuda, mostrar-fila, etc.)
- **Causa**: Cache do Discord ou comandos não sincronizados corretamente
- **Consequência**: Usuários não conseguem usar os comandos do bot

## Correções Aplicadas

### 1. Configuração do Fly.io (fly.toml)
✅ Adicionado `max_machines_running = 1` - garante apenas 1 máquina
✅ Aumentado intervalo do health check de 30s para 60s - evita timeouts
✅ Aumentado timeout do health check de 10s para 20s
✅ Mudado path do health check de `/ping` para `/health` (mais informativo)

### 2. Código do Bot (main.py)
✅ Modificado para rodar APENAS 1 bot no Fly.io (antes tentava rodar múltiplos)
✅ Adicionado `bot.tree.clear_commands()` antes do sync - limpa comandos antigos
✅ Melhorado health check com informações de status e quantidade de servidores
✅ Adicionado tratamento de erro no health check

## Como Aplicar as Correções

### Passo 1: Escalar para 1 Máquina (IMEDIATO)
```bash
cd botss
./fix-multiple-machines.sh
```

Este script vai:
- Listar todas as máquinas rodando
- Escalar para exatamente 1 máquina
- Verificar que ficou apenas 1

### Passo 2: Fazer Deploy das Mudanças
```bash
cd botss
./deploy-fly.sh
```

Ou manualmente:
```bash
cd botss
flyctl deploy
```

### Passo 3: Verificar se Funcionou
```bash
# Ver logs em tempo real
flyctl logs

# Verificar status
flyctl status

# Ver máquinas
flyctl machines list
```

Deve aparecer:
- ✅ Apenas 1 máquina rodando
- ✅ Sem erros de "sessão invalidada"
- ✅ Comandos sincronizados com sucesso
- ✅ Health check respondendo corretamente

## Comandos do Discord

Após o deploy, os comandos podem demorar até 1 hora para aparecer devido ao cache do Discord.

**Para forçar atualização imediata:**
1. Feche completamente o Discord (não minimizar)
2. Reabra o Discord
3. Ou use Ctrl+R para recarregar

**Comandos disponíveis:**
- /mostrar-fila - Criar fila de apostas
- /setup - Configurar servidor
- /ajuda - Ver todos comandos
- /confirmar-pagamento - Confirmar pagamento
- /finalizar-aposta - Finalizar aposta
- /cancelar-aposta - Cancelar aposta
- /historico - Ver histórico
- /minhas-apostas - Ver apostas ativas
- /sair-todas-filas - Sair de todas filas
- /desbugar-filas - Limpar filas (admin)

## Monitoramento

### Ver logs em tempo real:
```bash
flyctl logs
```

### Verificar health:
```bash
curl https://botss.fly.dev/health
```

Deve retornar:
```
Bot Status: online
Guilds: X
Uptime: OK
```

## Troubleshooting

### Se ainda aparecer "sessão invalidada":
1. Verifique se há múltiplas máquinas: `flyctl machines list`
2. Se tiver mais de 1, rode: `flyctl scale count 1 --yes`
3. Reinicie o app: `flyctl apps restart botss`

### Se comandos não aparecerem:
1. Verifique os logs: `flyctl logs` 
2. Procure por "comandos sincronizados globalmente"
3. Aguarde até 1 hora ou force reload no Discord (Ctrl+R)
4. Verifique se o bot está online no Discord

### Se health check falhar:
1. Verifique se a porta 8080 está configurada
2. Veja os logs para erros no servidor HTTP
3. Teste manualmente: `curl https://botss.fly.dev/health`

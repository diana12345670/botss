# 💰 Migrar para Replit Deploy - Solução Mais Barata

## 💸 Comparação de Custos

| Plataforma | Custo Mensal | Observações |
|------------|--------------|-------------|
| **Fly.io (atual)** | **$15/mês** ❌ | Muito caro! |
| **Fly.io (otimizado)** | $1-2/mês | Com 128MB RAM |
| **Replit Deploy** | **$0-2/mês** ✅ | Mais barato! |

## 🎯 Por que Replit Deploy é Melhor?

### 💰 Custo
- **Base:** $1/mês (vs $1-2/mês no Fly.io)
- **Compute:** $3.20 por milhão de unidades
- **Requests:** $1.20 por milhão de requests
- **Créditos gratuitos:** $25/mês com Replit Core ($20/mês)
- **RESULTADO:** Provavelmente **GRÁTIS** dentro dos créditos!

### ✅ Vantagens Adicionais
- ✅ **Integrado** - Já está no Replit
- ✅ **Sem configuração** - Deploy com 1 clique
- ✅ **Rollback automático** - Voltar para versões anteriores
- ✅ **Logs integrados** - Tudo no mesmo lugar
- ✅ **Secrets gerenciados** - DISCORD_TOKEN já configurado
- ✅ **PostgreSQL incluído** - Se precisar de banco

## 🚀 Como Migrar

### Passo 1: Preparar o Projeto

O bot já está pronto! Só precisa de pequenos ajustes:

1. **Criar arquivo `.replit`:**
```toml
run = "cd ap && python main.py"
modules = ["python-3.11"]

[deployment]
run = ["sh", "-c", "cd ap && python main.py"]
deploymentTarget = "autoscale"
```

2. **Atualizar configuração:**
O bot já detecta automaticamente se está no Replit ou Fly.io, então não precisa mudar código!

### Passo 2: Deploy no Replit

1. Clique no botão **"Deploy"** no topo direito do Replit
2. Escolha **"Autoscale Deployment"**
3. Configure:
   - **Name:** nz-apostas-bot
   - **Region:** Mais próxima (São Paulo se disponível)
   - **CPU:** 0.25 vCPU (suficiente)
   - **Memory:** 256MB
4. Clique em **"Deploy"**

### Passo 3: Verificar

1. Veja os logs no painel de deployment
2. Teste o bot no Discord
3. Monitore custos no dashboard

## 💡 Configuração Recomendada

### Para Bot Pequeno/Médio (até 10 servidores)
```
- CPU: 0.25 vCPU
- Memory: 256MB
- Custo estimado: $1-2/mês (dentro dos créditos gratuitos!)
```

### Para Bot Grande (10+ servidores)
```
- CPU: 0.5 vCPU
- Memory: 512MB
- Custo estimado: $3-5/mês
```

## 📊 Estimativa de Custo Real

Para um bot Discord médio:
- **Base fee:** $1/mês
- **Compute:** ~$0.50/mês (bot passa maior parte do tempo idle)
- **Requests:** ~$0.20/mês (baixo tráfego HTTP)
- **TOTAL:** ~$1.70/mês

Com Replit Core ($20/mês) que dá $25 em créditos:
- **Custo efetivo:** $0/mês (dentro dos créditos!)

## 🔄 E o Fly.io?

Depois de migrar para Replit:

1. **Parar o bot no Fly.io:**
```bash
flyctl scale count 0 -a botss
```

2. **Deletar a app (opcional):**
```bash
flyctl apps destroy botss
```

3. **Ou manter como backup:**
   - Deixe com 0 instâncias (custo $0)
   - Pode reativar se precisar

## ✅ Checklist de Migração

- [ ] Criar arquivo `.replit` com configuração de deployment
- [ ] Fazer deploy via botão "Deploy" no Replit
- [ ] Verificar se o bot conectou no Discord
- [ ] Testar comandos básicos (/ajuda, /mostrar-fila)
- [ ] Monitorar logs por 24h
- [ ] Parar bot no Fly.io (flyctl scale count 0)
- [ ] Verificar custos no Replit dashboard

## 🆘 Suporte

Se tiver problemas:
1. Veja logs do deployment no Replit
2. Verifique se DISCORD_TOKEN está configurado
3. Teste localmente primeiro (botão "Run" normal)

## 💰 Economia Final

**Fly.io atual:** $15/mês
**Replit Deploy:** $0-2/mês (provavelmente $0 com créditos)

**ECONOMIA: $13-15/mês (87-100%)** 🎉

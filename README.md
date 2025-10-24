# NZ Apostas - Bot Discord

Bot profissional de apostas para Discord com sistema de filas, mediação e histórico.

## Features

- ✅ Sistema de filas 1v1 e 2v2
- ✅ Mediação de apostas com confirmação de pagamento
- ✅ Múltiplos modos de jogo (Misto, Mob)
- ✅ Histórico de apostas
- ✅ Canais privados automáticos
- ✅ Sistema de PIX para mediadores
- ✅ Comandos administrativos

## Deploy

### Replit (Principal)

Este bot está configurado para rodar no Replit. Basta clicar no botão **Run** para iniciar.

**Variáveis de Ambiente:**
- `TOKEN`: Token do bot Discord

### Railway (Backup)

Para deploy no Railway, consulte o guia completo: [DEPLOY_RAILWAY.md](DEPLOY_RAILWAY.md)

## Comandos

### Jogadores
- `/confirmar-pagamento` - Confirmar envio do pagamento
- `/minhas-apostas` - Ver apostas ativas
- `/historico` - Ver histórico de apostas

### Moderadores
- `/mostrar-fila` - Criar fila com botões
- `/finalizar-aposta` - Declarar vencedor
- `/cancelar-aposta` - Cancelar aposta

### Administradores
- `/desbugar-filas` - Limpar sistema (emergência)

## Como Usar

1. Moderador cria fila com `/mostrar-fila`
2. Jogadores clicam em "Entrar na Fila" (1v1) ou escolhem time (2v2)
3. Sistema cria canal privado automaticamente
4. Mediador aceita e fornece PIX
5. Jogadores enviam pagamento e confirmam
6. Partida é liberada
7. Mediador declara vencedor com `/finalizar-aposta`

## Estrutura

```
nz-apostas/
├── main.py              # Bot principal
├── models/
│   └── bet.py          # Modelo de aposta
├── utils/
│   └── database.py     # Sistema de dados
├── data/
│   └── bets.json       # Dados persistentes
└── DEPLOY_RAILWAY.md   # Guia Railway
```

## Desenvolvimento

**Dependências:**
- Python 3.10
- discord.py 2.6.4

**Instalação Local:**
```bash
pip install discord.py
python main.py
```

## Troubleshooting

### 429 Too Many Requests
Se você receber este erro, veja: https://stackoverflow.com/questions/66724687/in-discord-py-how-to-solve-the-error-for-toomanyrequests

### Bot não conecta
- Verifique se o TOKEN está configurado
- Confirme que o bot tem as permissões necessárias no servidor

### Comandos não aparecem
- Aguarde até 1 hora para sincronização global
- Ou remova/readicione o bot ao servidor

## Suporte

Para dúvidas sobre configuração do bot Discord, consulte:
- [Documentação discord.py](https://discordpy.readthedocs.io/)
- [Discord Developer Portal](https://discord.com/developers/applications)

---

**Deploy Principal**: Replit  
**Deploy Backup**: Railway ([Ver guia](DEPLOY_RAILWAY.md))
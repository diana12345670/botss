# 🎮 NZ Apostado - Bot de Apostas Discord

Sistema completo de apostas para Discord com filas, mediadores e gerenciamento automático de canais.

## 📋 Funcionalidades Implementadas

✅ **Sistema de Filas por Modo**
- 1v1 Misto
- 1v1 Mob
- 2v2 Misto

✅ **Criação Automática de Canais Privados**
- Quando 2 jogadores entram na mesma fila, um canal privado é criado automaticamente
- Sistema de botão para ADMs aceitarem mediação
- Cada mediador insere sua própria chave PIX

✅ **Sistema de Confirmação de Pagamento**
- Cada jogador confirma que enviou o pagamento
- Mediador recebe notificações das confirmações

✅ **Finalização de Apostas**
- Mediador declara o vencedor
- Canal é automaticamente deletado após 30 segundos

✅ **Sistema Anti-Duplicação**
- Jogadores só podem estar em uma aposta ativa por vez

✅ **Logs e Histórico**
- Todas as apostas são registradas
- Histórico acessível por comando

## 🚀 Como Configurar

### 1. Habilitar Intents no Portal do Discord

**IMPORTANTE:** O bot precisa de intents privilegiados habilitados. Siga estes passos:

1. Acesse [Discord Developer Portal](https://discord.com/developers/applications/)
2. Selecione sua aplicação (bot)
3. Vá em **Bot** no menu lateral
4. Role até **Privileged Gateway Intents**
5. Habilite as seguintes opções:
   - ✅ **Presence Intent**
   - ✅ **Server Members Intent**
   - ✅ **Message Content Intent**
6. Clique em **Save Changes**

### 2. Convidar o Bot

Use este link para convidar o bot (substitua `YOUR_CLIENT_ID` pelo ID da sua aplicação):

```
https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=8&scope=bot%20applications.commands
```

### 3. Garantir Permissões de Administrador

O sistema identifica mediadores através de permissões de **Administrador** no Discord. Certifique-se de que os membros que devem mediar apostas tenham esse cargo.

## 📖 Comandos Disponíveis

### 👥 Comandos para Jogadores

- `/entrar-fila` - Entrar na fila de apostas
- `/sair-fila` - Sair da fila de apostas
- `/ver-filas` - Ver status das filas
- `/confirmar-pagamento` - Confirmar que enviou o pagamento
- `/minhas-apostas` - Ver suas apostas ativas
- `/historico` - Ver histórico de apostas
- `/ajuda` - Ver todos os comandos

### 👨‍⚖️ Comandos para Mediadores

- `/finalizar-aposta` - Finalizar aposta e declarar vencedor
- `/cancelar-aposta` - Cancelar uma aposta

## 🎯 Como Funciona

1. **Jogador entra na fila:**
   - Use `/entrar-fila` e escolha o modo
   - Aguarde outro jogador

2. **Canal privado é criado:**
   - Quando 2 jogadores estão na fila, um canal privado é criado
   - Mensagem é enviada marcando os Administradores
   - Aparece um botão verde "👨‍⚖️ Aceitar Mediação"

3. **ADM aceita mediar:**
   - Primeiro ADM que clicar no botão vira o mediador
   - Abre um formulário para ele inserir a chave PIX dele
   - Sistema automaticamente bloqueia outros ADMs de aceitar
   - Jogadores são notificados que um mediador aceitou

4. **Confirmação de pagamento:**
   - Ambos jogadores enviam o valor da aposta para o PIX do mediador
   - Cada um usa `/confirmar-pagamento` no canal privado
   - Mediador recebe notificação a cada confirmação

5. **Partida:**
   - Quando ambos confirmarem, a partida pode começar
   - Jogadores jogam a partida

6. **Finalização:**
   - Mediador usa `/finalizar-aposta @vencedor` para declarar o vencedor
   - Canal é automaticamente deletado após 30 segundos

## 📁 Estrutura do Projeto

```
.
├── main.py                 # Arquivo principal do bot
├── models/
│   ├── __init__.py
│   └── bet.py             # Modelo de dados das apostas
├── utils/
│   ├── __init__.py
│   └── database.py        # Gerenciamento de dados (JSON)
└── data/
    └── bets.json          # Armazenamento de apostas (criado automaticamente)
```

## 💾 Armazenamento de Dados

Os dados são armazenados em `data/bets.json` e incluem:

- **Filas ativas:** Jogadores aguardando em cada modo
- **Apostas ativas:** Apostas em andamento
- **Histórico:** Todas as apostas finalizadas

## ⚠️ Problemas Comuns

### Bot não responde aos comandos

1. Verifique se habilitou os intents privilegiados
2. Certifique-se de que o bot tem permissões de administrador no servidor
3. Aguarde alguns minutos após habilitar os intents

### Comandos não aparecem

1. Aguarde alguns minutos após adicionar o bot
2. Reinicie o Discord
3. Verifique se o bot está online

### Erro de permissões ao criar canais

O bot precisa de permissão de administrador ou pelo menos:
- Gerenciar Canais
- Criar Convites
- Enviar Mensagens
- Mencionar Todos

## 🔧 Personalização

Você pode personalizar:

1. **Modos de jogo:** Edite a lista `MODES` em `main.py`
2. **PIX do mediador:** Altere `MEDIATOR_PIX` em `main.py`
3. **Nome da categoria:** Altere `ACTIVE_BETS_CATEGORY` em `main.py`
4. **Tempo de deleção:** Altere o valor em `await asyncio.sleep(30)`

## 📝 Logs

O bot registra todas as atividades:
- Jogadores que entraram/saíram de filas
- Apostas criadas
- Confirmações de pagamento
- Apostas finalizadas
- Vencedores

## 🆘 Suporte

Se tiver problemas:

1. Verifique os logs do bot no console
2. Confirme que o TOKEN está configurado corretamente
3. Certifique-se de que os intents estão habilitados
4. Verifique as permissões do bot no servidor

## 📄 Licença

Este bot foi criado para uso pessoal/privado.

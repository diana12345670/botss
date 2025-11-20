
# 📖 Comandos do StormBet Apostas

Guia completo de todos os comandos disponíveis no bot.

## 📋 Índice

- [Comandos para Jogadores](#comandos-para-jogadores)
- [Comandos para Moderadores](#comandos-para-moderadores)
- [Comandos Administrativos](#comandos-administrativos)

## 👥 Comandos para Jogadores

### `/mostrar-fila`

Cria um painel interativo de filas com botões para entrada rápida.

**Uso:**
```
/mostrar-fila modo:[escolha] valor:[número] moeda:[escolha]
```

**Parâmetros:**
- `modo` - Tipo de jogo (1v1 Misto, 1v1 Mob, 2v2 Misto, 2v2 Mob)
- `valor` - Valor da aposta (número)
- `moeda` - Moeda (R$, USD, EUR, GBP, ARS, CLP)

**Exemplo:**
```
/mostrar-fila modo:1v1 Misto valor:50 moeda:R$
```

### `/preset-filas`

Cria painéis para todos os modos de uma vez (1v1 Misto, 1v1 Mob, 2v2 Misto, 2v2 Mob).

**Uso:**
```
/preset-filas valor:[número] moeda:[escolha]
```

**Exemplo:**
```
/preset-filas valor:100 moeda:R$
```

### `/confirmar-pagamento`

Confirma que você enviou o pagamento para o mediador.

**Uso:**
```
/confirmar-pagamento
```

**Importante:**
- Use apenas no canal privado da sua aposta
- Confirme somente após realmente enviar o pagamento
- Ambos os jogadores precisam confirmar para a partida começar

### `/minhas-apostas`

Mostra todas as suas apostas ativas no momento.

**Uso:**
```
/minhas-apostas
```

### `/historico`

Mostra seu histórico completo de apostas.

**Uso:**
```
/historico
```

**Informações mostradas:**
- Total de apostas
- Vitórias e derrotas
- Valor total ganho/perdido
- Últimas apostas detalhadas

### `/sair-todas-filas`

Remove você de todas as filas que está aguardando.

**Uso:**
```
/sair-todas-filas
```

**Nota:** Use se entrou em uma fila por engano ou mudou de ideia.

### `/ajuda`

Mostra lista completa de comandos disponíveis.

**Uso:**
```
/ajuda
```

## 👨‍⚖️ Comandos para Moderadores

### `/finalizar-aposta`

Declara o vencedor de uma aposta e finaliza o processo.

**Uso:**
```
/finalizar-aposta vencedor:@jogador
```

**Parâmetros:**
- `vencedor` - Mencione o jogador que venceu

**Importante:**
- Use apenas no canal privado da aposta
- Confira os resultados antes de finalizar
- O canal será deletado após 30 segundos

**Exemplo:**
```
/finalizar-aposta vencedor:@Jogador1
```

### `/cancelar-aposta`

Cancela uma aposta em andamento.

**Uso:**
```
/cancelar-aposta motivo:[texto]
```

**Parâmetros:**
- `motivo` - Razão do cancelamento (opcional)

**Quando usar:**
- Problemas técnicos
- Desistência de jogador
- Erro no sistema
- Solicitação de ambos os jogadores

**Exemplo:**
```
/cancelar-aposta motivo:Jogador desconectou
```

## 🔧 Comandos Administrativos

### `/setup`

Configura o bot no servidor (primeira vez).

**Uso:**
```
/setup
```

**Permissão:** Administrador

**O que faz:**
- Cria categoria "💰・Apostas Ativas"
- Define canal de filas
- Configura permissões

### `/desbugar-filas`

Limpa todo o sistema em caso de bug (use com cuidado).

**Uso:**
```
/desbugar-filas
```

**Permissão:** Administrador

**Aviso:** Este comando:
- Remove todos os jogadores de todas as filas
- Mantém apostas ativas intactas
- Deve ser usado apenas em emergências

### `/servidores`

Mostra informações sobre os servidores onde o bot está.

**Uso:**
```
/servidores
```

**Permissão:** Apenas desenvolvedores

## 💡 Dicas de Uso

### Para Jogadores

1. **Entrar na fila:**
   - Clique no botão "Entrar na Fila" no painel
   - Aguarde outro jogador
   - Você receberá uma notificação quando der match

2. **Confirmar pagamento:**
   - Envie o PIX para o mediador
   - Use `/confirmar-pagamento` no canal privado
   - Aguarde o outro jogador confirmar também

3. **Após a partida:**
   - Aguarde o mediador declarar o vencedor
   - O canal será deletado automaticamente

### Para Moderadores

1. **Aceitar mediação:**
   - Clique no botão "👨‍⚖️ Aceitar Mediação"
   - Insira sua chave PIX no formulário
   - Aguarde os jogadores confirmarem pagamento

2. **Finalizar aposta:**
   - Confira quem venceu
   - Use `/finalizar-aposta @vencedor`
   - Confira as informações antes de confirmar

3. **Em caso de problemas:**
   - Use `/cancelar-aposta` com motivo claro
   - Explique a situação aos jogadores
   - Devolva os valores se necessário

## ❓ Perguntas Frequentes

### Como entro em uma fila?
Clique no botão "Entrar na Fila" no painel criado com `/mostrar-fila`.

### Posso estar em várias filas ao mesmo tempo?
Não, você só pode estar em uma aposta ativa por vez.

### Como sei que meu pagamento foi confirmado?
O bot enviará uma mensagem de confirmação no canal privado.

### E se o mediador não responder?
Use `/cancelar-aposta` ou entre em contato com os administradores do servidor.

### Posso ver minhas apostas antigas?
Sim, use `/historico` para ver todo seu histórico.

## 🆘 Problemas Comuns

### Comando não aparece
- Aguarde alguns minutos após adicionar o bot
- Verifique se o bot tem as permissões necessárias
- Tente digitar `/` e procurar o comando

### Não consigo entrar na fila
- Verifique se não está em outra aposta ativa
- Use `/sair-todas-filas` para limpar
- Tente novamente

### Botão não funciona
- Aguarde alguns segundos e tente novamente
- Verifique sua conexão
- Se persistir, peça ao moderador para criar uma nova fila

---

**Precisa de mais ajuda?** Entre em contato com o suporte ou use `/ajuda` no Discord.

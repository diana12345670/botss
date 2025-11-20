
# 🎓 Tutorial Completo - StormBet Apostas

Aprenda a usar o bot passo a passo, desde a configuração até a finalização de apostas.

## 📋 Conteúdo

1. [Configuração Inicial](#configuração-inicial)
2. [Como Apostar (Jogadores)](#como-apostar-jogadores)
3. [Como Mediar (Moderadores)](#como-mediar-moderadores)
4. [Finalização e Histórico](#finalização-e-histórico)

## 🚀 Configuração Inicial

### Para Administradores do Servidor

#### Passo 1: Adicionar o Bot

1. Clique no link de convite do bot
2. Selecione seu servidor
3. Autorize as permissões solicitadas
4. Clique em "Autorizar"

#### Passo 2: Configurar o Bot

```
/setup
```

Isso criará:
- Categoria "💰・Apostas Ativas"
- Configurações de permissões
- Estrutura básica do sistema

#### Passo 3: Criar Painéis de Fila

**Opção 1: Painel Individual**
```
/mostrar-fila modo:1v1 Misto valor:50 moeda:R$
```

**Opção 2: Todos os Painéis de Uma Vez**
```
/preset-filas valor:50 moeda:R$
```

Isso criará 4 painéis (1v1 Misto, 1v1 Mob, 2v2 Misto, 2v2 Mob).

## 👥 Como Apostar (Jogadores)

### Passo 1: Entrar na Fila

1. Vá até o canal de filas
2. Encontre o painel do modo desejado
3. Clique no botão **"Entrar na Fila"**

**Para 1v1:**
```
✅ Você está aguardando na fila
```

**Para 2v2:**
```
Escolha seu time:
[Time 1] [Time 2]
```

### Passo 2: Aguardar Match

Quando outro(s) jogador(es) entrar(em), você receberá uma notificação:

```
@Você @Oponente

🎮 Aposta criada!
Modo: 1v1 Misto
Valor: R$ 50,00

Aguardando mediador aceitar...
```

### Passo 3: Aguardar Mediador

Um moderador verá a mensagem e clicará em **"👨‍⚖️ Aceitar Mediação"**.

O mediador inserirá a chave PIX dele.

### Passo 4: Enviar Pagamento

1. Copie a chave PIX fornecida
2. Envie o valor da aposta via PIX
3. **IMPORTANTE:** Após enviar, use o comando:

```
/confirmar-pagamento
```

### Passo 5: Aguardar Confirmação

Quando ambos os jogadores confirmarem:

```
✅ Pagamentos confirmados!

A partida pode começar. Boa sorte! 🎮
```

### Passo 6: Jogar a Partida

- Jogue sua partida normalmente
- O mediador estará acompanhando
- Não feche o canal privado

### Passo 7: Aguardar Resultado

O mediador declarará o vencedor:

```
🏆 Vencedor: @Jogador1

O canal será deletado em 30 segundos.
```

## 👨‍⚖️ Como Mediar (Moderadores)

### Passo 1: Aceitar Mediação

Quando uma aposta for criada, você verá:

```
@Moderadores

🎮 Nova aposta criada!
Modo: 1v1 Misto
Valor: R$ 50,00

[👨‍⚖️ Aceitar Mediação]
```

Clique no botão **"Aceitar Mediação"**.

### Passo 2: Inserir Chave PIX

Um formulário aparecerá:

```
📱 Insira sua chave PIX:
[_________________]
```

Digite sua chave PIX e envie.

### Passo 3: Aguardar Pagamentos

Os jogadores verão:

```
💰 Envie R$ 50,00 para:
PIX: sua.chave@exemplo.com

Após enviar, use /confirmar-pagamento
```

Você receberá notificações conforme eles confirmarem:

```
✅ @Jogador1 confirmou o pagamento
⏳ Aguardando @Jogador2...
```

### Passo 4: Verificar Pagamentos

- Confira se ambos os valores foram recebidos
- Verifique sua conta bancária
- Confirme os valores antes de liberar

### Passo 5: Liberar Partida

Quando ambos confirmarem e você verificar:

```
✅ Pagamentos confirmados!
A partida pode começar.
```

### Passo 6: Acompanhar Partida

- Fique atento ao resultado
- Peça prints se necessário
- Seja imparcial

### Passo 7: Declarar Vencedor

Após verificar o resultado:

```
/finalizar-aposta vencedor:@Jogador1
```

Confirme as informações e envie.

### Passo 8: Pagar Vencedor

- Envie o valor total (2x o valor da aposta) para o vencedor
- O canal será deletado em 30 segundos

## 📊 Finalização e Histórico

### Ver Suas Apostas Ativas

```
/minhas-apostas
```

Mostra todas as apostas onde você está participando no momento.

### Ver Histórico Completo

```
/historico
```

Mostra:
- Total de apostas
- Vitórias/Derrotas
- Valor total ganho/perdido
- Últimas 10 apostas detalhadas

### Sair de Filas

Se mudou de ideia:

```
/sair-todas-filas
```

Remove você de todas as filas.

## 💡 Dicas e Boas Práticas

### Para Jogadores

✅ **FAÇA:**
- Confirme pagamento apenas após realmente enviar
- Tire prints da transferência
- Seja respeitoso com outros jogadores
- Aguarde pacientemente o mediador

❌ **NÃO FAÇA:**
- Confirmar pagamento sem enviar
- Entrar em múltiplas filas
- Sair da fila após dar match
- Discutir com o mediador

### Para Mediadores

✅ **FAÇA:**
- Verifique os pagamentos antes de liberar
- Seja imparcial e justo
- Peça prints quando necessário
- Comunique-se claramente

❌ **NÃO FAÇA:**
- Mediar apostas de amigos próximos
- Favorecer nenhum jogador
- Liberar antes de confirmar pagamentos
- Demorar muito para declarar vencedor

## ⚠️ Situações Especiais

### Jogador Desistiu

```
/cancelar-aposta motivo:Jogador desistiu
```

### Problema Técnico

```
/cancelar-aposta motivo:Problema técnico no jogo
```

### Empate (decidir com os jogadores)

- Remarcar partida
- Ou dividir valores (mediador devolve metade para cada)

### Disputa de Resultado

1. Peça prints de ambos os lados
2. Analise com calma
3. Se necessário, chame outro moderador
4. Decisão do mediador é final

## 🆘 Problemas Comuns e Soluções

### "Você já está em uma aposta ativa"

**Solução:**
```
/sair-todas-filas
```

### "Botão não funciona"

**Solução:**
- Aguarde alguns segundos
- Tente novamente
- Se persistir, peça ao moderador para criar nova fila

### "Não recebi o match"

**Solução:**
- Verifique suas notificações do Discord
- Procure por canais novos em "💰・Apostas Ativas"
- Use `/minhas-apostas` para ver se há aposta ativa

### "Mediador não aceitou"

**Solução:**
- Aguarde, pode demorar alguns minutos
- Marque os moderadores se demorar muito
- Ou cancele e crie nova aposta

## 📚 Próximos Passos

Agora que você sabe usar o bot:

1. Pratique com apostas menores primeiro
2. Leia os [Termos de Uso](TERMOS.md)
3. Consulte o [FAQ](FAQ.md) para dúvidas
4. Entre em contato com suporte se precisar

---

**Boa sorte nas suas apostas! 🎮🏆**

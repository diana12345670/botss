# Correção: Botões Param de Funcionar Após 10 Minutos

## ❌ Problema

Quando você clica nos botões após 10 minutos (ou quando o bot reinicia no Fly.io), aparece "interação falhou".

## ✅ Solução Implementada

### 1. Custom IDs Persistentes

Adicionei `custom_id` a todos os botões para torná-los persistentes:

```python
@discord.ui.button(..., custom_id='persistent:join_queue')
@discord.ui.button(..., custom_id='persistent:join_team1')
@discord.ui.button(..., custom_id='persistent:join_team2')
@discord.ui.button(..., custom_id='persistent:leave_queue')
@discord.ui.button(..., custom_id='persistent:confirm_payment')
@discord.ui.button(..., custom_id='persistent:accept_mediation')
```

### 2. Registro de Views no on_ready

Quando o bot inicia, ele agora registra todas as Views:

```python
@bot.event
async def on_ready():
    # ... código existente ...
    
    # Registrar views persistentes
    bot.add_view(QueueButton(...))
    bot.add_view(ConfirmPaymentButton(...))
    bot.add_view(AcceptMediationButton(...))
```

## 🎯 Resultado

Com essas mudanças, os botões vão continuar funcionando:
- ✅ Após 10 minutos
- ✅ Após 1 hora
- ✅ Após o bot reiniciar
- ✅ Para sempre (enquanto a mensagem existir)

## 📦 Deploy da Correção

Para aplicar a correção no Fly.io:

```bash
export PATH="/home/runner/.fly/bin:$PATH"
cd botss
./fix-sleep.sh
```

Ou manualmente:

```bash
flyctl deploy --ha=false -a botss
```

## ✅ Como Testar

1. Crie uma fila com `/mostrar-fila`
2. Aguarde 10-15 minutos
3. Clique no botão "Entrar na Fila"
4. Deve funcionar normalmente! ✅

## 📋 O Que Mudou no Código

- ✅ Todos os botões agora têm `custom_id` único
- ✅ Views são registradas no `on_ready`
- ✅ Views têm `timeout=None` (já estava correto)
- ✅ Bot reconhece botões antigos após reiniciar

## 🚀 Status

Correção implementada e pronta para deploy!

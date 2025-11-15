import os
import sys
import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
import asyncio
from datetime import datetime
from models.bet import Bet
from utils.database import Database
from aiohttp import web

# Forçar logs para stdout sem buffer (ESSENCIAL para Fly.io)
import logging

# Configurar logging para capturar TUDO (incluindo discord.py)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ],
    force=True  # Força reconfiguração mesmo se já configurado
)

# Desabilitar buffering do Python completamente
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Logger do bot
logger = logging.getLogger('bot')
logger.setLevel(logging.INFO)

# Função para logging com flush automático (necessário para Fly.io)
def log(message):
    logger.info(message)
    sys.stdout.flush()
    sys.stderr.flush()

# Lock global para evitar race conditions na criação de apostas
queue_locks = {}
# Lock para proteção na criação de novos locks - INICIALIZADO AQUI
import asyncio as _asyncio_init
queue_locks_creation_lock = _asyncio_init.Lock()

# Detectar ambiente de execução
IS_FLYIO = os.getenv("FLY_APP_NAME") is not None
IS_RAILWAY = os.getenv("RAILWAY_ENVIRONMENT") is not None or os.getenv("RAILWAY_STATIC_URL") is not None

if IS_FLYIO:
    log("✈️ Detectado ambiente Fly.io")
elif IS_RAILWAY:
    log("🚂 Detectado ambiente Railway")
else:
    log("💻 Detectado ambiente Replit/Local")

# Configuração ULTRA otimizada de intents - apenas o mínimo necessário
intents = discord.Intents(
    guilds=True,           # Necessário para detectar servidores
    guild_messages=True,   # Necessário para mensagens
    members=True,          # Necessário para menções
    message_content=True   # Necessário para comandos
)
# Desabilitando TODOS eventos desnecessários para economizar RAM
intents.presences = False
intents.typing = False
intents.voice_states = False
intents.integrations = False
intents.webhooks = False
intents.invites = False
intents.emojis_and_stickers = False
intents.bans = False
intents.dm_messages = False
intents.dm_reactions = False
intents.dm_typing = False
intents.guild_reactions = False
intents.guild_typing = False
intents.moderation = False

# Bot com configurações de economia máxima
bot = commands.Bot(
    command_prefix="!",
    intents=intents,
    chunk_guilds_at_startup=False,  # Não carregar todos membros (economiza RAM)
    member_cache_flags=discord.MemberCacheFlags.none(),  # Sem cache de membros
    max_messages=10  # Cache ULTRA mínimo de mensagens (padrão é 1000)
)
db = Database()

MODES = ["1v1-misto", "1v1-mob", "2v2-misto", "2v2-mob"]
ACTIVE_BETS_CATEGORY = "Apostas Ativas"
EMBED_COLOR = 0x5865F2
CREATOR_FOOTER = "Bot de Apostado - Bot feito por SKplay. Todos os direitos reservados | Criador: <@1339336477661724674>"
CREATOR_ID = 1339336477661724674
AUTO_AUTHORIZED_GUILD_ID = 1438184380395687978  # Servidor auto-autorizado

# Dicionário para mapear queue_id -> (channel_id, message_id, mode, bet_value)
queue_messages = {}

# Helper para verificar se usuário é o criador
def is_creator(user_id: int) -> bool:
    """Verifica se o usuário é o criador do bot"""
    return user_id == CREATOR_ID

# Helper para verificar se servidor está autorizado
async def ensure_guild_authorized(guild: discord.Guild) -> bool:
    """Verifica se o servidor tem assinatura ativa, senão envia aviso e sai"""
    # Servidor auto-autorizado sempre tem acesso
    if guild.id == AUTO_AUTHORIZED_GUILD_ID:
        # Garante que tem assinatura permanente no banco
        if not db.is_subscription_active(guild.id):
            db.create_subscription(guild.id, None)  # Permanente
        return True
    
    if db.is_subscription_active(guild.id):
        return True
    
    log(f"❌ Servidor {guild.name} ({guild.id}) não autorizado")
    
    try:
        # Tenta encontrar um canal para enviar a mensagem
        channel = None
        if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            channel = guild.system_channel
        else:
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    channel = ch
                    break
        
        if channel:
            embed = discord.Embed(
                title="🔒 Servidor Não Autorizado",
                description="Este bot funciona apenas em servidores autorizados pelo criador.",
                color=0xFF0000
            )
            embed.add_field(
                name="📩 Para adicionar o bot:",
                value=(
                    "Fale diretamente comigo — [Discord DM](https://discord.com/users/1339336477661724674)\n"
                    "ou entre no meu servidor: https://discord.gg/yFhyc4RS5c"
                ),
                inline=False
            )
            embed.set_footer(text=CREATOR_FOOTER)
            
            await channel.send("@here", embed=embed)
            log(f"📨 Mensagem de aviso enviada para {guild.name}")
    except Exception as e:
        log(f"⚠️ Erro ao enviar mensagem de aviso: {e}")
    
    # Aguarda um pouco antes de sair
    await asyncio.sleep(3)
    
    try:
        await guild.leave()
        log(f"👋 Bot saiu do servidor {guild.name} ({guild.id})")
    except Exception as e:
        log(f"⚠️ Erro ao sair do servidor: {e}")
    
    return False

# Função para converter abreviações em valores numéricos
def parse_value(value_str: str) -> float:
    """
    Converte strings com abreviações em valores numéricos
    Exemplos:
        "50k" -> 50000
        "1.5m" -> 1500000
        "2.5b" -> 2500000000
        "1000" -> 1000
        "50" -> 50
    """
    if isinstance(value_str, (int, float)):
        return float(value_str)
    
    value_str = str(value_str).strip().lower().replace(',', '.')
    
    multipliers = {
        'k': 1_000,
        'm': 1_000_000,
        'b': 1_000_000_000
    }
    
    for suffix, multiplier in multipliers.items():
        if value_str.endswith(suffix):
            try:
                number = float(value_str[:-1])
                return number * multiplier
            except ValueError:
                pass
    
    try:
        return float(value_str)
    except ValueError:
        return 0.0

# Função para formatar valores em sonhos com k, m, b
def format_sonhos(value: float) -> str:
    """
    Formata valores monetários como sonhos com sufixos k/m/b
    Exemplos:
        500 -> 500
        1500 -> 1.5k
        999999 -> 999.9k (não arredonda para 1000k)
        1000000 -> 1m
        2500000000 -> 2.5b
    """
    import math

    if value >= 1_000_000_000:
        # Bilhões (limita a 999.9b máximo neste tier)
        num = value / 1_000_000_000
        # Trunca para 1 casa decimal para evitar arredondamento cruzando threshold
        num_truncated = math.floor(num * 10) / 10
        if num_truncated >= 10:
            formatted = f"{int(num_truncated)}b"
        else:
            formatted = f"{num_truncated:.1f}b".replace('.0b', 'b')
        return formatted
    elif value >= 1_000_000:
        # Milhões (limita a 999.9m máximo neste tier)
        num = value / 1_000_000
        # Trunca para 1 casa decimal
        num_truncated = math.floor(num * 10) / 10
        if num_truncated >= 10:
            formatted = f"{int(num_truncated)}m"
        else:
            formatted = f"{num_truncated:.1f}m".replace('.0m', 'm')
        return formatted
    elif value >= 1_000:
        # Milhares (limita a 999.9k máximo neste tier)
        num = value / 1_000
        # Trunca para 1 casa decimal
        num_truncated = math.floor(num * 10) / 10
        if num_truncated >= 10:
            formatted = f"{int(num_truncated)}k"
        else:
            formatted = f"{num_truncated:.1f}k".replace('.0k', 'k')
        return formatted
    else:
        # Valores menores que 1000
        if value == int(value):
            return f"{int(value)}"
        else:
            return f"{value:.2f}".replace('.', ',')


class QueueButton(discord.ui.View):
    def __init__(self, mode: str, bet_value: float, mediator_fee: float, message_id: int = None, currency_type: str = "sonhos"):
        super().__init__(timeout=None)
        self.mode = mode
        self.bet_value = bet_value
        self.mediator_fee = mediator_fee
        self.message_id = message_id
        self.currency_type = currency_type
        self.queue_id = f"{mode}_{message_id}" if message_id else ""

    async def update_queue_message(self, channel, guild_icon_url=None, original_message_id=None):
        """Atualiza a mensagem da fila com os jogadores atuais

        Args:
            channel: Canal onde a mensagem está
            guild_icon_url: URL do ícone do servidor (opcional)
            original_message_id: ID da mensagem original da fila (usado para buscar metadados após restart)
        """
        # Se não temos message_id na instância, tenta buscar dos metadados
        if not self.message_id and original_message_id:
            metadata = db.get_queue_metadata(original_message_id)
            if metadata:
                mode = metadata['mode']
                bet_value = metadata['bet_value']
                queue_id = metadata['queue_id']
                message_id = metadata['message_id']
                currency_type = metadata.get('currency_type', 'sonhos')
                log(f"📋 Metadados recuperados do banco para mensagem {original_message_id}")
            else:
                log(f"⚠️ update_queue_message: metadados não encontrados para mensagem {original_message_id}")
                return
        else:
            # Usa os valores da instância diretamente
            mode = self.mode
            bet_value = self.bet_value
            queue_id = self.queue_id
            message_id = self.message_id
            currency_type = self.currency_type

        if not message_id:
            log("⚠️ update_queue_message: message_id não disponível")
            return

        try:
            message = await channel.fetch_message(message_id)
            queue = db.get_queue(queue_id)

            log(f"📊 Atualizando fila {queue_id}: {len(queue)} jogadores restantes")

            # Usa menções diretas (sem fetch - mais rápido e econômico)
            player_names = [f"<@{user_id}>" for user_id in queue]
            players_text = "\n".join(player_names) if player_names else "Nenhum jogador na fila"

            # Formata o valor baseado no tipo de moeda
            if currency_type == "sonhos":
                valor_formatado = format_sonhos(bet_value)
                moeda_nome = "Sonhos"
            else:
                valor_formatado = f"R$ {bet_value:.2f}"
                moeda_nome = "Reais"

            embed_update = discord.Embed(
                title=mode.replace('-', ' ').title(),
                color=EMBED_COLOR
            )
            embed_update.add_field(name="Valor", value=valor_formatado, inline=True)
            embed_update.add_field(name="Moeda", value=moeda_nome, inline=True)
            embed_update.add_field(name="Fila", value=players_text if players_text != "Nenhum jogador na fila" else "Vazio", inline=False)
            if guild_icon_url:
                embed_update.set_thumbnail(url=guild_icon_url)
            embed_update.set_footer(text=CREATOR_FOOTER)

            await message.edit(embed=embed_update)
            log(f"✅ Mensagem da fila {queue_id} editada com sucesso")
        except Exception as e:
            log(f"❌ Erro ao atualizar mensagem da fila: {e}")

    @discord.ui.button(label='Entrar na Fila', style=discord.ButtonStyle.blurple, row=0, custom_id='persistent:join_queue')
    async def join_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        log(f"👆 Usuário {user_id} clicou em 'Entrar na Fila' (mensagem {interaction.message.id})")

        # DEFER IMEDIATAMENTE para evitar timeout de 3 segundos
        await interaction.response.defer(ephemeral=True)

        # Busca metadados da fila do banco de dados
        log(f"🔍 Buscando metadados para mensagem {interaction.message.id}")

        try:
            log(f"📊 Metadados disponíveis: {list(db.get_all_queue_metadata().keys())}")
            metadata = db.get_queue_metadata(interaction.message.id)
        except Exception as e:
            log(f"❌ ERRO ao buscar metadados: {e}")
            logger.exception("Stacktrace completo:")
            await interaction.followup.send(
                "Erro ao acessar dados da fila. Tente novamente em alguns segundos.",
                ephemeral=True
            )
            return

        if metadata:
            mode = metadata['mode']
            bet_value = metadata['bet_value']
            mediator_fee = metadata['mediator_fee']
            queue_id = metadata['queue_id']
            currency_type = metadata.get('currency_type', 'sonhos')
            log(f"✅ Metadados encontrados: queue_id={queue_id}, bet_value={bet_value}, mediator_fee={mediator_fee}, currency={currency_type}")
        else:
            # CRÍTICO: Se não encontrou metadados, aborta (não usa valores zero!)
            log(f"❌ ERRO: Metadados não encontrados para mensagem {interaction.message.id}")
            log(f"📋 Metadados disponíveis no banco: {list(db.get_all_queue_metadata().keys())}")
            await interaction.followup.send(
                "Erro: Esta fila não está mais disponível. Por favor, peça ao mediador para criar uma nova fila com /mostrar-fila.",
                ephemeral=True
            )
            return

        if db.is_user_in_active_bet(user_id):
            await interaction.followup.send(
                "Você já está em uma aposta ativa. Finalize ela antes de entrar em outra fila.",
                ephemeral=True
            )
            return

        # Adquire lock para esta fila para evitar race conditions
        # Protege a criação do lock com um lock global
        if queue_id not in queue_locks:
            async with queue_locks_creation_lock:
                # Double-check após adquirir o lock
                if queue_id not in queue_locks:
                    queue_locks[queue_id] = asyncio.Lock()

        async with queue_locks[queue_id]:
            # Recarrega a fila dentro do lock
            queue = db.get_queue(queue_id)
            log(f"📊 Fila {queue_id} antes de adicionar: {queue}")

            if user_id in queue:
                log(f"⚠️ Usuário {user_id} já está na fila {queue_id}")
                await interaction.followup.send(
                    "Você já está nesta fila.",
                    ephemeral=True
                )
                return

            # Adiciona à fila
            log(f"➕ Adicionando usuário {user_id} à fila {queue_id}")
            db.add_to_queue(queue_id, user_id)
            queue = db.get_queue(queue_id)
            log(f"📊 Fila {queue_id} após adicionar: {queue}")

        # Verifica se tem 2 jogadores para criar aposta
        if len(queue) >= 2:
                log(f"🎯 2 jogadores encontrados na fila {queue_id}! Iniciando criação de aposta...")
                log(f"💰 Valores antes de criar tópico: bet_value={bet_value} (type={type(bet_value)}), mediator_fee={mediator_fee} (type={type(mediator_fee)})")

                # Garante conversão para float
                bet_value = float(bet_value)
                mediator_fee = float(mediator_fee)
                log(f"💰 Valores após conversão: bet_value={bet_value}, mediator_fee={mediator_fee}")

                player1_id = queue[0]
                player2_id = queue[1]

                # Envia mensagem de confirmação (sem validar se estão no servidor)
                player1_mention = f"<@{player1_id}>"
                player2_mention = f"<@{player2_id}>"
                embed = discord.Embed(
                    title="Aposta encontrada",
                    description=f"Criando tópico para {player1_mention} vs {player2_mention}...",
                    color=EMBED_COLOR
                )
                if interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                embed.set_footer(text=CREATOR_FOOTER)

                try:
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    log(f"✅ Mensagem de confirmação enviada")
                except Exception as e:
                    log(f"⚠️ Erro ao enviar mensagem de confirmação: {e}")

                # Remove os jogadores da fila
                db.remove_from_queue(queue_id, player1_id)
                db.remove_from_queue(queue_id, player2_id)
                log(f"🗑️ Removidos {player1_id} e {player2_id} da fila {queue_id}")

                # Atualiza a mensagem MANUALMENTE após remover os jogadores
                try:
                    # Recarrega a fila atualizada (sem os 2 jogadores)
                    updated_queue = db.get_queue(queue_id)
                    log(f"📊 Fila após remoção: {updated_queue}")

                    message = await interaction.channel.fetch_message(interaction.message.id)

                    # Monta a lista de jogadores restantes
                    player_names = [f"<@{uid}>" for uid in updated_queue]
                    players_text = "\n".join(player_names) if player_names else "Vazio"

                    log(f"📝 Atualizando painel para: {players_text}")

                    # Formata valor baseado no tipo de moeda
                    if currency_type == "sonhos":
                        valor_formatado = format_sonhos(bet_value)
                        moeda_nome = "Sonhos"
                    else:
                        valor_formatado = f"R$ {bet_value:.2f}"
                        moeda_nome = "Reais"

                    embed_update = discord.Embed(
                        title=mode.replace('-', ' ').title(),
                        color=EMBED_COLOR
                    )
                    embed_update.add_field(name="Valor", value=valor_formatado, inline=True)
                    embed_update.add_field(name="Moeda", value=moeda_nome, inline=True)
                    embed_update.add_field(name="Fila", value=players_text, inline=False)
                    if interaction.guild.icon:
                        embed_update.set_thumbnail(url=interaction.guild.icon.url)
                    embed_update.set_footer(text=CREATOR_FOOTER)

                    await message.edit(embed=embed_update)
                    log(f"✅ Painel atualizado - jogadores removidos visualmente")
                except Exception as e:
                    log(f"❌ Erro ao atualizar mensagem da fila: {e}")
                    logger.exception("Stacktrace:")

                # Passa o ID do canal atual para criar o tópico nele
                log(f"🏗️ Iniciando criação do tópico com valores: bet_value={bet_value}, mediator_fee={mediator_fee}")
                try:
                    await create_bet_channel(interaction.guild, mode, player1_id, player2_id, bet_value, mediator_fee, interaction.channel_id)
                    log(f"✅ Tópico criado com sucesso!")
                except Exception as e:
                    log(f"❌ ERRO ao criar tópico: {e}")
                    logger.exception("Stacktrace completo:")

                    # Se falhou, retorna os jogadores para a fila
                    db.add_to_queue(queue_id, player1_id)
                    db.add_to_queue(queue_id, player2_id)
                    log(f"♻️ Jogadores retornados à fila após erro")

                    # Atualiza a mensagem novamente
                    try:
                        guild_icon = interaction.guild.icon.url if interaction.guild.icon else None
                        await self.update_queue_message(interaction.channel, guild_icon, interaction.message.id)
                    except:
                        pass
        else:
                # Apenas entrou na fila (menos de 2 jogadores)
                embed = discord.Embed(
                    title="Entrou na fila",
                    description=f"{mode.replace('-', ' ').title()} - {len(queue)}/2",
                    color=EMBED_COLOR
                )
                if interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                embed.set_footer(text=CREATOR_FOOTER)

                await interaction.followup.send(embed=embed, ephemeral=True)

                # Atualiza a mensagem principal com os nomes REAIS dos jogadores
                try:
                    # Recarrega a fila para garantir dados atualizados
                    queue = db.get_queue(queue_id)
                    log(f"📊 Atualizando painel - fila atual: {queue}")

                    message = await interaction.channel.fetch_message(interaction.message.id)

                    player_names = [f"<@{uid}>" for uid in queue]
                    players_text = "\n".join(player_names) if player_names else "Vazio"

                    log(f"📝 Texto a ser exibido no painel: {players_text}")

                    # Formata valor baseado no tipo de moeda
                    if currency_type == "sonhos":
                        valor_formatado = format_sonhos(bet_value)
                        moeda_nome = "Sonhos"
                    else:
                        valor_formatado = f"R$ {bet_value:.2f}"
                        moeda_nome = "Reais"

                    embed_update = discord.Embed(
                        title=mode.replace('-', ' ').title(),
                        color=EMBED_COLOR
                    )
                    embed_update.add_field(name="Valor", value=valor_formatado, inline=True)
                    embed_update.add_field(name="Moeda", value=moeda_nome, inline=True)
                    embed_update.add_field(name="Fila", value=players_text, inline=False)
                    if interaction.guild.icon:
                        embed_update.set_thumbnail(url=interaction.guild.icon.url)
                    embed_update.set_footer(text=CREATOR_FOOTER)

                    await message.edit(embed=embed_update)
                    log(f"✅ Painel atualizado com sucesso")
                except Exception as e:
                    log(f"❌ Erro ao atualizar mensagem da fila: {e}")
                    logger.exception("Stacktrace:")

    @discord.ui.button(label='Sair da Fila', style=discord.ButtonStyle.gray, row=0, custom_id='persistent:leave_queue')
    async def leave_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        log(f"👆 Usuário {user_id} clicou em 'Sair da Fila' (mensagem {interaction.message.id})")

        # Busca metadados da fila do banco de dados
        metadata = db.get_queue_metadata(interaction.message.id)
        if metadata:
            queue_id = metadata['queue_id']
            log(f"✅ Metadados encontrados: queue_id={queue_id}")
        else:
            queue_id = self.queue_id
            log(f"⚠️ Metadados não encontrados, usando self.queue_id={queue_id}")

        queue = db.get_queue(queue_id)
        log(f"📊 Fila {queue_id} atual: {queue}")

        if user_id not in queue:
            log(f"⚠️ Usuário {user_id} NÃO está na fila {queue_id}")
            await interaction.response.send_message(
                "Você não está nesta fila.",
                ephemeral=True
            )
            return

        log(f"➖ Removendo usuário {user_id} da fila {queue_id}")
        db.remove_from_queue(queue_id, user_id)

        # Verifica se foi removido
        queue_after = db.get_queue(queue_id)
        log(f"📊 Fila {queue_id} após remover: {queue_after}")

        embed = discord.Embed(
            title="Saiu da fila",
            color=EMBED_COLOR
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=CREATOR_FOOTER)

        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Atualiza a mensagem principal com a fila atualizada
        try:
            metadata = db.get_queue_metadata(interaction.message.id)
            if metadata:
                mode = metadata['mode']
                bet_value = metadata['bet_value']
                currency_type = metadata.get('currency_type', 'sonhos')
            else:
                mode = self.mode
                bet_value = self.bet_value
                currency_type = self.currency_type

            message = await interaction.channel.fetch_message(interaction.message.id)

            # Lista atualizada de jogadores
            player_names = [f"<@{uid}>" for uid in queue_after]
            players_text = "\n".join(player_names) if player_names else "Vazio"

            log(f"📝 Atualizando painel após saída: {players_text}")

            # Formata valor baseado no tipo de moeda
            if currency_type == "sonhos":
                valor_formatado = format_sonhos(bet_value)
                moeda_nome = "Sonhos"
            else:
                valor_formatado = f"R$ {bet_value:.2f}"
                moeda_nome = "Reais"

            embed_update = discord.Embed(
                title=mode.replace('-', ' ').title(),
                color=EMBED_COLOR
            )
            embed_update.add_field(name="Valor", value=valor_formatado, inline=True)
            embed_update.add_field(name="Moeda", value=moeda_nome, inline=True)
            embed_update.add_field(name="Fila", value=players_text, inline=False)
            if interaction.guild.icon:
                embed_update.set_thumbnail(url=interaction.guild.icon.url)
            embed_update.set_footer(text=CREATOR_FOOTER)

            await message.edit(embed=embed_update)
            log(f"✅ Painel atualizado após saída")
        except Exception as e:
            log(f"❌ Erro ao atualizar painel: {e}")
            logger.exception("Stacktrace:")


class ConfirmPaymentButton(discord.ui.View):
    def __init__(self, bet_id: str):
        super().__init__(timeout=None)
        self.bet_id = bet_id

    @discord.ui.button(label='Confirmar Pagamento', style=discord.ButtonStyle.green, custom_id='persistent:confirm_payment')
    async def confirm_payment_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        log(f"🔍 Botão 'Confirmar Pagamento' clicado - bet_id={self.bet_id}")
        bet = db.get_active_bet(self.bet_id)

        if not bet:
            log(f"❌ Aposta não encontrada: bet_id={self.bet_id}")
            # Tenta buscar pelo canal como fallback
            bet = db.get_bet_by_channel(interaction.channel_id)
            if bet:
                log(f"✅ Aposta encontrada pelo canal: {bet.bet_id}")
                self.bet_id = bet.bet_id
            else:
                log(f"❌ Aposta não encontrada nem por bet_id nem por channel_id")
                await interaction.response.send_message(
                    "Esta aposta não foi encontrada.\n"
                    "Use o comando /confirmar-pagamento dentro do tópico da aposta.",
                    ephemeral=True
                )
                return
        else:
            log(f"✅ Aposta encontrada: {bet.bet_id}")

        if bet.mediator_id == 0:
            await interaction.response.send_message(
                "Aguarde um mediador aceitar esta aposta antes de confirmar pagamento.",
                ephemeral=True
            )
            return

        user_id = interaction.user.id

        if user_id == bet.player1_id:
            if bet.player1_confirmed:
                await interaction.response.send_message(
                    "Você já confirmou seu pagamento.",
                    ephemeral=True
                )
                return

            bet.player1_confirmed = True
            db.update_active_bet(bet)

            # Usa menção direta (economiza chamadas API)
            embed = discord.Embed(
                title="Pagamento Confirmado",
                description=f"<@{bet.player1_id}>",
                color=EMBED_COLOR
            )
            embed.set_footer(text=CREATOR_FOOTER)
            await interaction.response.send_message(embed=embed)

        elif user_id == bet.player2_id:
            if bet.player2_confirmed:
                await interaction.response.send_message(
                    "Você já confirmou seu pagamento.",
                    ephemeral=True
                )
                return

            bet.player2_confirmed = True
            db.update_active_bet(bet)

            # Usa menção direta (economiza chamadas API)
            embed = discord.Embed(
                title="Pagamento Confirmado",
                description=f"<@{bet.player2_id}>",
                color=EMBED_COLOR
            )
            embed.set_footer(text=CREATOR_FOOTER)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                "Você não é um dos jogadores desta aposta.",
                ephemeral=True
            )
            return

        if bet.is_fully_confirmed():
            # Usa menções diretas (economiza chamadas API)
            embed = discord.Embed(
                title="Pagamentos Confirmados",
                description="Partida liberada",
                color=EMBED_COLOR
            )
            embed.set_footer(text=CREATOR_FOOTER)

            await interaction.channel.send(embed=embed)


class PixModal(discord.ui.Modal, title='Inserir Chave PIX'):
    pix_key = discord.ui.TextInput(
        label='Chave PIX',
        placeholder='Digite sua chave PIX (CPF, telefone, email, etc)',
        required=True,
        max_length=100
    )

    def __init__(self, bet_id: str):
        super().__init__()
        self.bet_id = bet_id

    async def on_submit(self, interaction: discord.Interaction):
        bet = db.get_active_bet(self.bet_id)
        if not bet:
            await interaction.response.send_message("Aposta não encontrada.", ephemeral=True)
            return

        if bet.mediator_id != 0:
            # Usa menção direta (economiza chamadas API)
            await interaction.response.send_message(
                f"Esta aposta já tem um mediador: <@{bet.mediator_id}>",
                ephemeral=True
            )
            return

        bet.mediator_id = interaction.user.id
        bet.mediator_pix = str(self.pix_key.value)
        db.update_active_bet(bet)

        # Usa menções diretas (economiza chamadas API)
        embed = discord.Embed(
            title="Mediador Aceito",
            color=EMBED_COLOR
        )
        embed.add_field(name="Modo", value=bet.mode.replace("-", " ").title(), inline=True)
        embed.add_field(name="Jogadores", value=f"<@{bet.player1_id}> vs <@{bet.player2_id}>", inline=False)
        embed.add_field(name="Mediador", value=interaction.user.mention, inline=True)
        embed.add_field(name="PIX", value=f"`{bet.mediator_pix}`", inline=True)
        embed.add_field(name="Instrução", value="Envie o pagamento e clique no botão abaixo para confirmar", inline=False)
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=CREATOR_FOOTER)

        confirm_view = ConfirmPaymentButton(self.bet_id)
        await interaction.response.send_message(embed=embed, view=confirm_view)

        try:
            original_message = await interaction.channel.fetch_message(interaction.message.id)
            await original_message.edit(view=None)
        except discord.NotFound:
            log("Mensagem original não encontrada (já deletada)")
        except Exception as e:
            log(f"Erro ao remover botões da mensagem original: {e}")

        # Busca o tópico (thread) da aposta
        thread = interaction.guild.get_thread(bet.channel_id)
        if not thread:
            # Tenta buscar threads arquivados
            try:
                thread = await interaction.guild.fetch_channel(bet.channel_id)
            except discord.NotFound:
                log(f"Thread {bet.channel_id} não encontrado (já deletado)")
            except Exception as e:
                log(f"Erro ao buscar thread: {e}")

        if thread:
            # Adiciona o mediador ao tópico
            await thread.add_user(interaction.user)

            # Envia uma mensagem no tópico mencionando os jogadores
            await thread.send(f"<@{bet.player1_id}> <@{bet.player2_id}> Um mediador aceitou a aposta! ✅")


async def accept_bet_with_sonhos(interaction: discord.Interaction, bet_id: str):
    """Aceita mediação de aposta em Sonhos (sem PIX)"""
    bet = db.get_active_bet(bet_id)
    if not bet:
        await interaction.response.send_message("Aposta não encontrada.", ephemeral=True)
        return

    if bet.mediator_id != 0:
        await interaction.response.send_message(
            f"Esta aposta já tem um mediador: <@{bet.mediator_id}>",
            ephemeral=True
        )
        return

    # Aceita como mediador SEM pedir PIX
    bet.mediator_id = interaction.user.id
    bet.mediator_pix = "SONHOS_VIA_LORITTA"  # Marcador especial
    db.update_active_bet(bet)

    # Formata valores
    valor_total = format_sonhos(bet.bet_value)
    taxa_mediador = format_sonhos(bet.mediator_fee)

    embed = discord.Embed(
        title="Mediador Aceito - Aposta em Sonhos",
        color=EMBED_COLOR
    )
    embed.add_field(name="Modo", value=bet.mode.replace("-", " ").title(), inline=True)
    embed.add_field(name="Jogadores", value=f"<@{bet.player1_id}> vs <@{bet.player2_id}>", inline=False)
    embed.add_field(name="Mediador", value=interaction.user.mention, inline=True)
    embed.add_field(name="Valor por Jogador", value=valor_total, inline=True)
    embed.add_field(name="Taxa do Mediador", value=taxa_mediador, inline=True)
    embed.add_field(
        name="📋 Instruções",
        value=f"1. Use o comando da Loritta para transferir **{valor_total}** Sonhos para o mediador {interaction.user.mention}\n"
              f"2. Após transferir, clique no botão **'Confirmar Pagamento'** abaixo",
        inline=False
    )
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=CREATOR_FOOTER)

    confirm_view = ConfirmPaymentButton(bet_id)
    await interaction.response.send_message(embed=embed, view=confirm_view)

    # Remove botões da mensagem original
    try:
        original_message = await interaction.channel.fetch_message(interaction.message.id)
        await original_message.edit(view=None)
    except:
        pass

    # Adiciona mediador ao tópico e notifica jogadores
    thread = interaction.guild.get_thread(bet.channel_id)
    if not thread:
        try:
            thread = await interaction.guild.fetch_channel(bet.channel_id)
        except:
            pass

    if thread:
        await thread.add_user(interaction.user)
        await thread.send(
            f"<@{bet.player1_id}> <@{bet.player2_id}> Um mediador aceitou a aposta em Sonhos! ✅\n\n"
            f"**Próximo passo:** Transfiram **{valor_total}** Sonhos para {interaction.user.mention} usando a Loritta."
        )


class AcceptMediationButton(discord.ui.View):
    def __init__(self, bet_id: str):
        super().__init__(timeout=None)
        self.bet_id = bet_id

    @discord.ui.button(label='Aceitar Mediação', style=discord.ButtonStyle.green, custom_id='persistent:accept_mediation')
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        log(f"🔍 Botão 'Aceitar Mediação' clicado - bet_id={self.bet_id}")
        bet = db.get_active_bet(self.bet_id)

        if not bet:
            log(f"❌ Aposta não encontrada: bet_id={self.bet_id}")
            # Tenta buscar pelo canal como fallback
            bet = db.get_bet_by_channel(interaction.channel_id)
            if bet:
                log(f"✅ Aposta encontrada pelo canal: {bet.bet_id}")
                self.bet_id = bet.bet_id
            else:
                log(f"❌ Aposta não encontrada nem por bet_id nem por channel_id")
                await interaction.response.send_message(
                    "Esta aposta não foi encontrada.",
                    ephemeral=True
                )
                return
        else:
            log(f"✅ Aposta encontrada: {bet.bet_id}")

        if bet.mediator_id != 0:
            log(f"⚠️ Aposta já tem mediador: {bet.mediator_id}")
            await interaction.response.send_message("Esta aposta já tem um mediador.", ephemeral=True)
            return

        mediator_role_id = db.get_mediator_role(interaction.guild.id)
        has_mediator_role = mediator_role_id and discord.utils.get(interaction.user.roles, id=mediator_role_id) is not None

        if not has_mediator_role:
            if mediator_role_id:
                await interaction.response.send_message(
                    f"Você precisa ter o cargo <@&{mediator_role_id}> para aceitar mediação.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "Este servidor ainda não configurou um cargo de mediador.\n"
                    "Um administrador deve usar /setup @cargo para configurar.",
                    ephemeral=True
                )
            return

        # Detecta o tipo de moeda da aposta
        currency_type = getattr(bet, 'currency_type', 'sonhos')
        
        if currency_type == "sonhos":
            # Aposta em Sonhos - aceita SEM pedir PIX
            log(f"💎 Aceitando mediação de aposta em Sonhos (sem PIX)")
            await accept_bet_with_sonhos(interaction, self.bet_id)
        else:
            # Aposta em Reais - pede PIX do mediador
            log(f"💵 Aceitando mediação de aposta em Reais (com PIX)")
            await interaction.response.send_modal(PixModal(self.bet_id))

    @discord.ui.button(label='Cancelar Aposta', style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        bet = db.get_active_bet(self.bet_id)

        if not bet:
            await interaction.response.send_message("Aposta não encontrada.", ephemeral=True)
            return

        # Verifica se tem o cargo de mediador configurado
        mediator_role_id = db.get_mediator_role(interaction.guild.id)
        has_mediator_role = mediator_role_id and discord.utils.get(interaction.user.roles, id=mediator_role_id) is not None

        if not has_mediator_role:
            if mediator_role_id:
                await interaction.response.send_message(
                    f"Você precisa ter o cargo <@&{mediator_role_id}> para cancelar apostas.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "Este servidor ainda não configurou um cargo de mediador.\n"
                    "Um administrador deve usar /setup @cargo para configurar.",
                    ephemeral=True
                )
            return

        # Usa menções diretas (economiza chamadas API)
        embed = discord.Embed(
            title="Aposta Cancelada",
            description=f"<@{bet.player1_id}> e <@{bet.player2_id}>",
            color=EMBED_COLOR
        )
        embed.set_footer(text=CREATOR_FOOTER)

        await interaction.response.send_message(embed=embed)

        bet.finished_at = datetime.now().isoformat()
        db.finish_bet(bet)

        await asyncio.sleep(10)

        try:
            # Arquiva e bloqueia o tópico ao invés de deletar
            if isinstance(interaction.channel, discord.Thread):
                await interaction.channel.edit(archived=True, locked=True)
        except:
            pass


async def cleanup_orphaned_data_task():
    """Tarefa em background que limpa dados órfãos a cada 10 minutos"""
    await bot.wait_until_ready()
    log("🧹 Iniciando limpeza de dados órfãos (a cada 10 minutos)")

    while not bot.is_closed():
        try:
            # Aguarda 10 minutos
            await asyncio.sleep(600)

            # Limpa dados órfãos
            cleaned = db.cleanup_orphaned_data()
            if cleaned:
                log("🧹 Dados órfãos removidos (economia de espaço)")
        except Exception as e:
            log(f"Erro na limpeza de dados órfãos: {e}")
            await asyncio.sleep(600)

async def cleanup_expired_queues():
    """Tarefa em background que remove jogadores que ficaram muito tempo na fila"""
    await bot.wait_until_ready()
    log("🧹 Iniciando sistema de limpeza automática de filas (5 minutos)")

    while not bot.is_closed():
        try:
            # Busca jogadores expirados (mais de 5 minutos na fila)
            expired_players = db.get_expired_queue_players(timeout_minutes=5)

            if expired_players:
                log(f"🧹 Encontrados jogadores expirados em {len(expired_players)} filas")

                for queue_id, user_ids in expired_players.items():
                    # Remove cada jogador expirado
                    for user_id in user_ids:
                        db.remove_from_queue(queue_id, user_id)
                        log(f"⏱️ Removido usuário {user_id} da fila {queue_id} (timeout)")
                    
                    # Log para debug: mostra estado da fila após remoções
                    updated_queue = db.get_queue(queue_id)
                    log(f"🔍 Fila {queue_id} após remoções: {len(updated_queue)} jogadores")

                    # Limpa filas completamente vazias e seu metadata
                    if not updated_queue:
                        # Extrai message_id do queue_id (formato: "mode_message_id")
                        parts = queue_id.split('_')
                        if len(parts) >= 2:
                            try:
                                message_id = int(parts[-1])
                                db.delete_queue_metadata(message_id)
                                # Limpa do dicionário em memória (previne memory leak)
                                if queue_id in queue_messages:
                                    del queue_messages[queue_id]
                                log(f"🧹 Metadata e memória limpos para fila vazia {queue_id}")
                            except ValueError:
                                pass

                    # Atualiza a mensagem da fila se possível
                    if queue_id in queue_messages:
                        channel_id, message_id, mode, bet_value = queue_messages[queue_id]
                        try:
                            channel = bot.get_channel(channel_id)
                            if channel:
                                message = await channel.fetch_message(message_id)

                                # Verifica se é 2v2 ou 1v1
                                is_2v2 = "2v2" in mode

                                if is_2v2:
                                    team1_queue = db.get_queue(f"{queue_id}_team1")
                                    team2_queue = db.get_queue(f"{queue_id}_team2")

                                    # Usa menções diretas (economiza API calls)
                                    team1_text = "\n".join([f"<@{uid}>" for uid in team1_queue]) if team1_queue else "Nenhum jogador"
                                    team2_text = "\n".join([f"<@{uid}>" for uid in team2_queue]) if team2_queue else "Nenhum jogador"

                                    embed = discord.Embed(
                                        title=mode.replace('-', ' ').title(),
                                        color=EMBED_COLOR
                                    )
                                    embed.add_field(name="Valor", value=format_sonhos(bet_value), inline=True)
                                    embed.add_field(name="Time 1", value=team1_text, inline=True)
                                    embed.add_field(name="Time 2", value=team2_text, inline=True)
                                    if channel.guild and channel.guild.icon:
                                        embed.set_thumbnail(url=channel.guild.icon.url)
                                else:
                                    current_queue = db.get_queue(queue_id)
                                    log(f"🔍 Atualizando painel {queue_id}: {len(current_queue)} jogadores na fila")

                                    # Usa menções diretas (economiza API calls)
                                    players_text = "\n".join([f"<@{uid}>" for uid in current_queue]) if current_queue else "Vazio"

                                    embed = discord.Embed(
                                        title=mode.replace('-', ' ').title(),
                                        color=EMBED_COLOR
                                    )
                                    embed.add_field(name="Valor", value=format_sonhos(bet_value), inline=True)
                                    embed.add_field(name="Fila", value=players_text, inline=True)
                                    if channel.guild and channel.guild.icon:
                                        embed.set_thumbnail(url=channel.guild.icon.url)

                                await message.edit(embed=embed)
                                log(f"✅ Painel {queue_id} atualizado com sucesso")
                        except Exception as e:
                            log(f"Erro ao atualizar mensagem da fila {queue_id}: {e}")

            # Aguarda 60 segundos antes de verificar novamente (economiza processamento)
            await asyncio.sleep(60)

        except Exception as e:
            log(f"Erro na limpeza de filas: {e}")
            await asyncio.sleep(60)


@bot.event
async def on_message_delete(message):
    """Detecta quando uma mensagem de painel é deletada e limpa os dados da fila"""
    try:
        # Verifica se a mensagem deletada tinha metadados de fila
        metadata = db.get_queue_metadata(message.id)

        if metadata:
            queue_id = metadata['queue_id']
            log(f"🗑️ Mensagem de painel deletada (ID: {message.id})")
            log(f"🧹 Limpando dados da fila {queue_id}...")

            # Remove metadados
            db.delete_queue_metadata(message.id)

            # Remove do dicionário em memória
            if queue_id in queue_messages:
                del queue_messages[queue_id]

            # Limpa a fila (remove todos jogadores)
            data = db._load_data()
            if queue_id in data.get('queues', {}):
                del data['queues'][queue_id]
            if queue_id in data.get('queue_timestamps', {}):
                del data['queue_timestamps'][queue_id]
            db._save_data(data)

            log(f"✅ Fila {queue_id} completamente removida (economia de espaço)")
    except Exception as e:
        log(f"⚠️ Erro ao processar mensagem deletada: {e}")

@bot.event
async def on_guild_join(guild: discord.Guild):
    """Quando o bot entra em um servidor, verifica se está autorizado"""
    log(f"➕ Bot adicionado ao servidor: {guild.name} ({guild.id})")
    
    # Verifica se o servidor está autorizado
    if not await ensure_guild_authorized(guild):
        log(f"❌ Servidor {guild.name} não está autorizado, saindo...")

@bot.event
async def on_ready():
    log("=" * 50)
    log("✅ BOT CONECTADO AO DISCORD!")
    log("=" * 50)
    log(f'👤 Usuário: {bot.user}')
    log(f'📛 Nome: {bot.user.name}')
    log(f'🆔 ID: {bot.user.id}')
    log(f'🌐 Servidores: {len(bot.guilds)}')

    try:
        log("🔄 Sincronizando comandos slash...")
        # Sincroniza globalmente (incluindo DM) - None = global
        synced_global = await bot.tree.sync(guild=None)
        log(f'✅ {len(synced_global)} comandos sincronizados globalmente (DM incluída)')
        for cmd in synced_global:
            log(f'  - /{cmd.name}')
        log('⏰ Comandos podem demorar até 1 hora para aparecer em DM (cache do Discord)')
    except Exception as e:
        log(f'⚠️ Erro ao sincronizar comandos: {e}')
        logger.exception("Stacktrace:")
        # Não falha o startup por causa de erro de sync

    # Registrar views persistentes (para botões não expirarem)
    log('📋 Registrando views persistentes...')

    # Registra apenas UMA VEZ cada view persistente
    # IMPORTANTE: Não criar novas instâncias, reutilizar as mesmas
    if not hasattr(bot, '_persistent_views_registered'):
        bot.add_view(QueueButton(mode="", bet_value=0, mediator_fee=0, currency_type="sonhos"))
        bot.add_view(ConfirmPaymentButton(bet_id=""))
        bot._persistent_views_registered = True
        log('✅ Views persistentes registradas')
    else:
        log('ℹ️ Views persistentes já estavam registradas')

    # Recuperar metadados de filas existentes após restart
    if not hasattr(bot, '_queue_metadata_recovered'):
        log('🔄 Recuperando metadados de filas existentes...')
        all_metadata = db.get_all_queue_metadata()

        # PASSO 1: Limpar jogadores que estão em apostas ativas das filas
        active_bets = db.get_all_active_bets()
        active_players = set()
        for bet in active_bets.values():
            active_players.add(bet.player1_id)
            active_players.add(bet.player2_id)

        log(f'🧹 Limpando {len(active_players)} jogadores que estão em apostas ativas')
        for player_id in active_players:
            db.remove_from_all_queues(player_id)

        # PASSO 2: Recuperar metadados e popular queue_messages
        for message_id_str, metadata in all_metadata.items():
            queue_id = metadata['queue_id']
            channel_id = metadata['channel_id']
            message_id = metadata['message_id']
            mode = metadata['mode']
            bet_value = metadata['bet_value']

            # Restaura no dicionário em memória
            queue_messages[queue_id] = (channel_id, message_id, mode, bet_value)

            # Log detalhado de cada fila recuperada
            current_queue = db.get_queue(queue_id)
            log(f'📋 Fila {queue_id}: {len(current_queue)} jogadores')

        log(f'✅ {len(all_metadata)} filas recuperadas e sincronizadas')
        bot._queue_metadata_recovered = True

    # Inicia a tarefa de limpeza automática de filas (apenas uma vez)
    if not hasattr(bot, '_cleanup_task_started'):
        bot.loop.create_task(cleanup_expired_queues())
        bot.loop.create_task(cleanup_orphaned_data_task())
        bot._cleanup_task_started = True
        log('🧹 Tarefas de limpeza iniciadas')
    else:
        log('ℹ️ Tarefas de limpeza já estavam rodando')
    
    # Task de verificação de assinaturas agora é iniciada em run_single_bot_instance
    # para funcionar com múltiplos bots
    # if not hasattr(bot, '_subscription_task_started'):
    #     check_expired_subscriptions.start()
    #     bot._subscription_task_started = True
    #     log('🔐 Tarefa de verificação de assinaturas iniciada')
    
    # Garante assinatura permanente do servidor auto-autorizado
    if not hasattr(bot, '_auto_authorized_setup'):
        auto_guild = bot.get_guild(AUTO_AUTHORIZED_GUILD_ID)
        if auto_guild:
            if not db.is_subscription_active(AUTO_AUTHORIZED_GUILD_ID):
                db.create_subscription(AUTO_AUTHORIZED_GUILD_ID, None)
                log(f"✅ Assinatura permanente automática criada para {auto_guild.name}")
        bot._auto_authorized_setup = True
    
    # Verifica servidores sem assinatura (apenas na primeira vez)
    if not hasattr(bot, '_initial_guild_check'):
        log('🔍 Verificando autorização dos servidores atuais...')
        unauthorized_guilds = []
        for guild in bot.guilds:
            # Pula o servidor auto-autorizado
            if guild.id == AUTO_AUTHORIZED_GUILD_ID:
                continue
            
            if not db.is_subscription_active(guild.id):
                log(f"⚠️ Servidor sem assinatura detectado: {guild.name} ({guild.id})")
                unauthorized_guilds.append(guild)
        
        # Processa servidores não autorizados com delay para evitar rate limiting
        async def process_unauthorized_guilds():
            for i, guild in enumerate(unauthorized_guilds):
                await ensure_guild_authorized(guild)
                # Aguarda 2 segundos entre cada remoção para evitar rate limit
                if i < len(unauthorized_guilds) - 1:
                    await asyncio.sleep(2)
        
        if unauthorized_guilds:
            bot.loop.create_task(process_unauthorized_guilds())
        
        bot._initial_guild_check = True
        log('✅ Verificação inicial de servidores concluída')


@bot.tree.command(name="mostrar-fila", description="[MODERADOR] Criar mensagem com botão para entrar na fila")
@app_commands.describe(
    modo="Escolha o modo de jogo",
    valor="Valor da aposta (exemplo: 50k, 1.5m, 2000)",
    taxa="Taxa do mediador (exemplo: 5%, 500, 1k)",
    moeda="Tipo de moeda da aposta (Reais ou Sonhos)"
)
@app_commands.choices(modo=[
    app_commands.Choice(name="1v1 Misto", value="1v1-misto"),
    app_commands.Choice(name="1v1 Mob", value="1v1-mob"),
    app_commands.Choice(name="2v2 Misto", value="2v2-misto"),
    app_commands.Choice(name="2v2 Mob", value="2v2-mob"),
])
@app_commands.choices(moeda=[
    app_commands.Choice(name="Reais", value="reais"),
    app_commands.Choice(name="Sonhos", value="sonhos"),
])
async def mostrar_fila(interaction: discord.Interaction, modo: app_commands.Choice[str], valor: str, taxa: str, moeda: app_commands.Choice[str]):
    # Busca o cargo de mediador configurado
    mediator_role_id = db.get_mediator_role(interaction.guild.id)

    # Verifica se tem o cargo de mediador configurado
    has_mediator_role = mediator_role_id and discord.utils.get(interaction.user.roles, id=mediator_role_id) is not None

    if not has_mediator_role:
        if mediator_role_id:
            await interaction.response.send_message(
                f"Você precisa ter o cargo <@&{mediator_role_id}> para usar este comando.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Este servidor ainda não configurou um cargo de mediador.\n"
                "Um administrador deve usar /setup @cargo para configurar.",
                ephemeral=True
            )
        return

    mode = modo.value
    currency_type = moeda.value
    
    # Converte o valor usando a função parse_value
    valor_numerico = parse_value(valor)
    
    if valor_numerico <= 0:
        await interaction.response.send_message(
            "Valor inválido. Use valores positivos (exemplos: 50k, 1.5m, 2000).",
            ephemeral=True
        )
        return
    
    # Processa a taxa (pode ser porcentagem ou valor fixo)
    taxa_str = str(taxa).strip()
    if taxa_str.endswith('%'):
        # Remove o % e calcula a porcentagem do valor
        try:
            percentual = float(taxa_str[:-1])
            taxa_numerica = (percentual / 100) * valor_numerico
        except ValueError:
            await interaction.response.send_message(
                "Taxa inválida. Use valores como: 5%, 500, 1k",
                ephemeral=True
            )
            return
    else:
        # Converte usando parse_value
        taxa_numerica = parse_value(taxa_str)
    
    if taxa_numerica < 0:
        await interaction.response.send_message(
            "Taxa inválida. Use valores não-negativos (exemplos: 5%, 500, 1k).",
            ephemeral=True
        )
        return

    # Formata o valor baseado no tipo de moeda
    if currency_type == "sonhos":
        valor_formatado = format_sonhos(valor_numerico)
    else:
        valor_formatado = f"R$ {valor_numerico:.2f}"

    embed = discord.Embed(
        title=modo.name,
        color=EMBED_COLOR
    )

    embed.add_field(name="Valor", value=valor_formatado, inline=True)
    embed.add_field(name="Moeda", value=moeda.name, inline=True)
    embed.add_field(name="Fila", value="Vazio", inline=False)
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=CREATOR_FOOTER)

    # Defer a resposta para evitar timeout
    await interaction.response.defer()

    # Envia a mensagem primeiro
    message = await interaction.followup.send(embed=embed, wait=True)

    log(f"Mensagem da fila criada com ID: {message.id}")

    # Cria o view COM o message_id correto
    view = QueueButton(mode, valor_numerico, taxa_numerica, message.id, currency_type)

    # Salva os metadados da fila no banco de dados ANTES de editar a mensagem
    queue_id = f"{mode}_{message.id}"
    db.save_queue_metadata(message.id, mode, valor_numerico, taxa_numerica, interaction.channel.id, currency_type)
    log(f"Metadados salvos: queue_id={queue_id}, bet_value={valor_numerico}, mediator_fee={taxa_numerica}, currency={currency_type}")

    # Salva a informação da fila em memória
    queue_messages[queue_id] = (interaction.channel.id, message.id, mode, valor_numerico, currency_type)
    log(f"Fila registrada em memória: {queue_id}")

    # Agora edita a mensagem com os botões
    await message.edit(embed=embed, view=view)
    log(f"Fila criada e pronta para uso: {mode} com moeda {currency_type}")






async def create_bet_channel(guild: discord.Guild, mode: str, player1_id: int, player2_id: int, bet_value: float, mediator_fee: float, source_channel_id: int = None):
    log(f"🔧 create_bet_channel chamada: mode={mode}, player1={player1_id}, player2={player2_id}, bet_value={bet_value}, mediator_fee={mediator_fee}")

    # VALIDAÇÃO CRÍTICA: Nunca permitir valores zero
    if bet_value <= 0 or mediator_fee < 0:
        log(f"❌ ERRO CRÍTICO: Valores inválidos - bet_value={bet_value}, mediator_fee={mediator_fee}. Abortando criação.")
        return

    # Validação dupla com lock para evitar race condition
    if db.is_user_in_active_bet(player1_id) or db.is_user_in_active_bet(player2_id):
        log(f"❌ Um dos jogadores já está em uma aposta ativa. Abortando criação.")
        return

    db.remove_from_all_queues(player1_id)
    db.remove_from_all_queues(player2_id)
    log(f"✅ Jogadores removidos de todas as filas")

    try:
        # Usa get_member ao invés de fetch_member (mais rápido, sem API call)
        log(f"🔍 Buscando membros do servidor...")
        player1 = guild.get_member(player1_id)
        player2 = guild.get_member(player2_id)

        # Se não encontrou no cache, só então faz fetch
        if not player1:
            log(f"🔄 Player1 não no cache, fazendo fetch...")
            player1 = await guild.fetch_member(player1_id)
        if not player2:
            log(f"🔄 Player2 não no cache, fazendo fetch...")
            player2 = await guild.fetch_member(player2_id)

        log(f"✅ Jogadores encontrados: {player1.name} e {player2.name}")

        # Busca o canal de origem (onde foi usado /mostrar-fila)
        log(f"🔍 Buscando canal de origem: {source_channel_id}")
        source_channel = guild.get_channel(source_channel_id) if source_channel_id else None

        if not source_channel:
            log(f"❌ Canal de origem {source_channel_id} não encontrado. Abortando criação.")
            db.add_to_queue(mode, player1_id)
            db.add_to_queue(mode, player2_id)
            return

        log(f"✅ Canal de origem encontrado: {source_channel.name}")

        # Criar tópico ao invés de canal
        thread_name = f"Aposta: {player1.name} vs {player2.name}"
        log(f"🏗️ Tentando criar tópico: {thread_name}")

        try:
            # Cria um tópico privado
            log(f"🔐 Tentando criar tópico PRIVADO...")
            thread = await source_channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.private_thread,
                auto_archive_duration=1440,  # 24 horas
                invitable=False
            )
            log(f"✅ Tópico PRIVADO criado: {thread_name} (ID: {thread.id})")
        except discord.Forbidden as e:
            log(f"❌ Sem permissão para criar tópico privado: {e}")
            log(f"🔄 Tentando criar tópico PÚBLICO como fallback...")
            try:
                # Fallback: tentar criar tópico público
                thread = await source_channel.create_thread(
                    name=thread_name,
                    auto_archive_duration=1440
                )
                log(f"✅ Tópico PÚBLICO criado: {thread_name} (ID: {thread.id})")
            except Exception as e:
                log(f"❌ Erro ao criar tópico público: {e}")
                logger.exception("Stacktrace:")
                raise
        except Exception as e:
            log(f"❌ Erro inesperado ao criar tópico: {e}")
            logger.exception("Stacktrace:")
            raise

        # Adiciona os jogadores ao tópico
        try:
            await thread.add_user(player1)
            await thread.add_user(player2)
            log(f"✅ Jogadores adicionados ao tópico")
        except Exception as e:
            log(f"⚠️ Erro ao adicionar jogadores ao tópico: {e}")

        bet_id = f"{player1_id}_{player2_id}_{int(datetime.now().timestamp())}"

        # Log final antes de criar o objeto Bet
        log(f"💰 Criando objeto Bet com valores: bet_value={bet_value}, mediator_fee={mediator_fee}")
        log(f"🆔 Thread criado com ID: {thread.id} (type={type(thread.id)})")

        # Busca o tipo de moeda do metadata da fila usando o source_channel_id
        # Como já temos o queue_id no formato mode_message_id, vamos buscar no metadados globais
        currency_type = 'sonhos'  # Valor padrão
        
        # Tenta encontrar nos metadados salvos
        all_metadata = db.get_all_queue_metadata()
        for msg_id, meta in all_metadata.items():
            if meta.get('mode') == mode and meta.get('channel_id') == source_channel_id:
                currency_type = meta.get('currency_type', 'sonhos')
                break
        
        bet = Bet(
            bet_id=bet_id,
            mode=mode,
            player1_id=player1_id,
            player2_id=player2_id,
            mediator_id=0,
            channel_id=thread.id,
            bet_value=float(bet_value),
            mediator_fee=float(mediator_fee),
            currency_type=currency_type
        )
        db.add_active_bet(bet)

        log(f"✅ Bet criado e salvo no banco:")
        log(f"   - bet_id: {bet.bet_id}")
        log(f"   - channel_id: {bet.channel_id}")
        log(f"   - bet_value: {bet.bet_value}")
        log(f"   - mediator_fee: {bet.mediator_fee}")
    except Exception as e:
        log(f"Erro ao criar tópico de aposta: {e}")
        db.add_to_queue(mode, player1_id)
        db.add_to_queue(mode, player2_id)
        return

    # Busca o cargo de mediador configurado
    mediator_role_id = db.get_mediator_role(guild.id)

    if mediator_role_id:
        mediator_role = guild.get_role(mediator_role_id)
        admin_mention = mediator_role.mention if mediator_role else "@Mediadores"
    else:
        admin_mention = "@Mediadores (configure com /setup)"

    # Log para debug - verificar valores recebidos
    log(f"💰 Criando embed com valores: bet_value={bet_value}, mediator_fee={mediator_fee}")

    # Formata valores usando a função format_sonhos
    valor_formatado = format_sonhos(float(bet_value))
    taxa_formatada = format_sonhos(float(mediator_fee))

    log(f"💰 Valores formatados: {valor_formatado} / {taxa_formatada}")

    embed = discord.Embed(
        title="Aposta - Aguardando Mediador",
        description=admin_mention,
        color=EMBED_COLOR
    )
    embed.add_field(name="Modo", value=mode.replace("-", " ").title(), inline=True)
    embed.add_field(name="Valor da Aposta", value=valor_formatado, inline=True)
    embed.add_field(name="Taxa do Mediador", value=taxa_formatada, inline=True)
    embed.add_field(name="Jogadores", value=f"{player1.mention} vs {player2.mention}", inline=False)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text=CREATOR_FOOTER)

    view = AcceptMediationButton(bet_id)

    await thread.send(content=f"{player1.mention} {player2.mention} Aposta criada! Aguardando mediador... {admin_mention}", embed=embed, view=view)


@bot.tree.command(name="confirmar-pagamento", description="Confirmar que você enviou o pagamento ao mediador")
async def confirmar_pagamento(interaction: discord.Interaction):
    log(f"🔍 /confirmar-pagamento chamado no canal {interaction.channel_id} por usuário {interaction.user.id}")
    bet = db.get_bet_by_channel(interaction.channel_id)

    if not bet:
        log(f"❌ Aposta não encontrada para canal {interaction.channel_id}")
        await interaction.response.send_message(
            "Este canal não é uma aposta ativa.\n"
            "Use este comando dentro do tópico da aposta.",
            ephemeral=True
        )
        return

    log(f"✅ Aposta encontrada: {bet.bet_id}")

    if bet.mediator_id == 0:
        await interaction.response.send_message(
            "Aguarde um mediador aceitar esta aposta antes de confirmar pagamento.",
            ephemeral=True
        )
        return

    user_id = interaction.user.id

    if user_id == bet.player1_id:
        if bet.player1_confirmed:
            await interaction.response.send_message(
                "Você já confirmou seu pagamento.",
                ephemeral=True
            )
            return

        bet.player1_confirmed = True
        db.update_active_bet(bet)

        player1 = await interaction.guild.fetch_member(bet.player1_id)
        mediator = await interaction.guild.fetch_member(bet.mediator_id)

        embed = discord.Embed(
            title="Pagamento Confirmado",
            description=player1.mention,
            color=EMBED_COLOR
        )
        await interaction.response.send_message(embed=embed)

    elif user_id == bet.player2_id:
        if bet.player2_confirmed:
            await interaction.response.send_message(
                "Você já confirmou seu pagamento.",
                ephemeral=True
            )
            return

        bet.player2_confirmed = True
        db.update_active_bet(bet)

        player2 = await interaction.guild.fetch_member(bet.player2_id)
        mediator = await interaction.guild.fetch_member(bet.mediator_id)

        embed = discord.Embed(
            title="Pagamento Confirmado",
            description=player2.mention,
            color=EMBED_COLOR
        )
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(
            "Você não é um dos jogadores desta aposta.",
            ephemeral=True
        )
        return

    if bet.is_fully_confirmed():
        player1 = await interaction.guild.fetch_member(bet.player1_id)
        player2 = await interaction.guild.fetch_member(bet.player2_id)

        embed = discord.Embed(
            title="Pagamentos Confirmados",
            description="Partida liberada",
            color=EMBED_COLOR
        )

        await interaction.channel.send(embed=embed)


@bot.tree.command(name="finalizar-aposta", description="[MEDIADOR] Finalizar a aposta e declarar vencedor")
@app_commands.describe(vencedor="Mencione o jogador vencedor")
async def finalizar_aposta(interaction: discord.Interaction, vencedor: discord.Member):
    log(f"🔍 /finalizar-aposta chamado")
    log(f"   - Canal ID: {interaction.channel_id} (type={type(interaction.channel_id)})")
    log(f"   - Canal: {interaction.channel}")
    log(f"   - É Thread? {isinstance(interaction.channel, discord.Thread)}")

    bet = db.get_bet_by_channel(interaction.channel_id)

    if not bet:
        log(f"❌ Aposta não encontrada para canal {interaction.channel_id}")
        # Lista todas as apostas ativas para debug
        all_bets = db.get_all_active_bets()
        log(f"📊 Apostas ativas: {len(all_bets)}")
        for bet_id, active_bet in all_bets.items():
            log(f"  - Bet {bet_id}: canal={active_bet.channel_id} (type={type(active_bet.channel_id)})")

        await interaction.response.send_message(
            "Este tópico não é uma aposta ativa.\n"
            "Verifique se você está no tópico correto da aposta.",
            ephemeral=True
        )
        return

    log(f"✅ Aposta encontrada: {bet.bet_id}")

    # Verifica se é o mediador da aposta OU se tem o cargo de mediador
    mediator_role_id = db.get_mediator_role(interaction.guild.id)
    has_mediator_role = mediator_role_id and discord.utils.get(interaction.user.roles, id=mediator_role_id) is not None
    is_bet_mediator = interaction.user.id == bet.mediator_id

    if not is_bet_mediator and not has_mediator_role:
        await interaction.response.send_message(
            "Apenas o mediador desta aposta ou membros com o cargo de mediador podem finalizá-la.",
            ephemeral=True
        )
        return

    if vencedor.id not in [bet.player1_id, bet.player2_id]:
        await interaction.response.send_message(
            "O vencedor deve ser um dos jogadores desta aposta.",
            ephemeral=True
        )
        return

    bet.winner_id = vencedor.id
    bet.finished_at = datetime.now().isoformat()

    # Usa menções diretas (economiza chamadas API)
    loser_id = bet.player1_id if vencedor.id == bet.player2_id else bet.player2_id

    embed = discord.Embed(
        title="Vencedor",
        description=vencedor.mention,
        color=EMBED_COLOR
    )
    embed.add_field(name="Modo", value=bet.mode.replace("-", " ").title(), inline=True)
    embed.add_field(name="Perdedor", value=f"<@{loser_id}>", inline=True)
    embed.set_footer(text=CREATOR_FOOTER)

    await interaction.response.send_message(embed=embed)

    db.finish_bet(bet)

    # Envia resultado no canal configurado (se houver)
    results_channel_id = db.get_results_channel(interaction.guild.id)
    if results_channel_id:
        try:
            results_channel = bot.get_channel(results_channel_id)
            if results_channel:
                # Cria embed para o canal de resultados
                results_embed = discord.Embed(
                    title="Resultado da Partida",
                    color=EMBED_COLOR
                )
                results_embed.add_field(name="Vencedor", value=vencedor.mention, inline=True)
                results_embed.add_field(name="Perdedor", value=f"<@{loser_id}>", inline=True)
                results_embed.add_field(name="Modo", value=bet.mode.replace("-", " ").title(), inline=True)
                results_embed.add_field(name="Valor", value=format_sonhos(bet.bet_value), inline=True)
                results_embed.add_field(name="Mediador", value=f"<@{bet.mediator_id}>", inline=True)
                if interaction.guild.icon:
                    results_embed.set_thumbnail(url=interaction.guild.icon.url)
                results_embed.set_footer(text=CREATOR_FOOTER)
                
                await results_channel.send(embed=results_embed)
                log(f"📢 Resultado enviado ao canal {results_channel.name}")
        except Exception as e:
            log(f"⚠️ Erro ao enviar resultado para canal: {e}")

    import asyncio
    await asyncio.sleep(10)

    try:
        # Arquiva e bloqueia o tópico ao invés de deletar
        if isinstance(interaction.channel, discord.Thread):
            await interaction.channel.edit(archived=True, locked=True)
    except discord.HTTPException as e:
        log(f"Não foi possível arquivar thread (permissões ou thread já arquivado): {e.status}")
    except Exception as e:
        log(f"Erro ao arquivar thread: {e}")


@bot.tree.command(name="cancelar-aposta", description="[MEDIADOR] Cancelar uma aposta em andamento")
async def cancelar_aposta(interaction: discord.Interaction):
    log(f"🔍 /cancelar-aposta chamado")
    log(f"   - Canal ID: {interaction.channel_id} (type={type(interaction.channel_id)})")
    log(f"   - É Thread? {isinstance(interaction.channel, discord.Thread)}")

    bet = db.get_bet_by_channel(interaction.channel_id)

    if not bet:
        log(f"❌ Aposta não encontrada para canal {interaction.channel_id}")
        all_bets = db.get_all_active_bets()
        log(f"📊 Apostas ativas: {len(all_bets)}")
        for bet_id, active_bet in all_bets.items():
            log(f"  - Bet {bet_id}: canal={active_bet.channel_id}")

        await interaction.response.send_message(
            "Este tópico não é uma aposta ativa.\n"
            "Verifique se você está no tópico correto da aposta.",
            ephemeral=True
        )
        return

    log(f"✅ Aposta encontrada: {bet.bet_id}")

    # Verifica se é o mediador da aposta OU se tem o cargo de mediador
    mediator_role_id = db.get_mediator_role(interaction.guild.id)
    has_mediator_role = mediator_role_id and discord.utils.get(interaction.user.roles, id=mediator_role_id) is not None
    is_bet_mediator = interaction.user.id == bet.mediator_id

    if not is_bet_mediator and not has_mediator_role:
        await interaction.response.send_message(
            "Apenas o mediador desta aposta ou membros com o cargo de mediador podem cancelá-la.",
            ephemeral=True
        )
        return

    player1 = await interaction.guild.fetch_member(bet.player1_id)
    player2 = await interaction.guild.fetch_member(bet.player2_id)

    embed = discord.Embed(
        title="❌ Aposta Cancelada",
        description=f"{player1.mention} e {player2.mention}",
        color=EMBED_COLOR
    )
    embed.set_footer(text=CREATOR_FOOTER)

    await interaction.response.send_message(embed=embed)

    bet.finished_at = datetime.now().isoformat()
    db.finish_bet(bet)

    import asyncio
    await asyncio.sleep(10)

    try:
        # Arquiva e bloqueia o tópico ao invés de deletar
        if isinstance(interaction.channel, discord.Thread):
            await interaction.channel.edit(archived=True, locked=True)
    except discord.HTTPException as e:
        log(f"Não foi possível arquivar thread (permissões ou thread já arquivado): {e.status}")
    except Exception as e:
        log(f"Erro ao arquivar thread: {e}")


@bot.tree.command(name="historico", description="Ver o histórico de apostas")
async def historico(interaction: discord.Interaction):
    history = db.get_bet_history()

    if not history:
        await interaction.response.send_message(
            "Ainda não há histórico de apostas.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="Histórico de Apostas",
        description=f"Total de apostas: {len(history)}",
        color=EMBED_COLOR
    )

    for bet in history[-10:]:
        winner_mention = f"<@{bet.winner_id}>" if bet.winner_id else "Cancelada"
        embed.add_field(
            name=f"{bet.mode.replace('-', ' ').title()}",
            value=(
                f"Jogadores: <@{bet.player1_id}> vs <@{bet.player2_id}>\n"
                f"Vencedor: {winner_mention}\n"
                f"Data: {bet.finished_at[:10] if bet.finished_at else 'N/A'}"
            ),
            inline=False
        )
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=CREATOR_FOOTER)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="minhas-apostas", description="Ver suas apostas ativas")
async def minhas_apostas(interaction: discord.Interaction):
    user_id = interaction.user.id
    active_bets = db.get_all_active_bets()

    user_bets = [bet for bet in active_bets.values() 
                 if bet.player1_id == user_id or bet.player2_id == user_id]

    if not user_bets:
        await interaction.response.send_message(
            "Você não tem apostas ativas no momento.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="Suas Apostas Ativas",
        description=f"Você tem {len(user_bets)} aposta(s) ativa(s)",
        color=EMBED_COLOR
    )

    for bet in user_bets:
        channel = f"<#{bet.channel_id}>"
        status = "Confirmada" if (
            (user_id == bet.player1_id and bet.player1_confirmed) or 
            (user_id == bet.player2_id and bet.player2_confirmed)
        ) else "Aguardando confirmação"

        embed.add_field(
            name=f"{bet.mode.replace('-', ' ').title()}",
            value=f"Canal: {channel}\nStatus: {status}",
            inline=False
        )
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=CREATOR_FOOTER)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="sair-todas-filas", description="Sair de todas as filas em que você está")
async def sair_todas_filas(interaction: discord.Interaction):
    user_id = interaction.user.id

    # Remove o usuário de todas as filas
    db.remove_from_all_queues(user_id)

    embed = discord.Embed(
        title="Removido de todas as filas",
        description="Você foi removido de todas as filas. Agora você pode entrar novamente.",
        color=EMBED_COLOR
    )
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=CREATOR_FOOTER)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="desbugar-filas", description="[ADMIN] Cancelar todas as apostas ativas e limpar filas")
async def desbugar_filas(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "Apenas administradores podem usar este comando.",
            ephemeral=True
        )
        return

    active_bets = db.get_all_active_bets()
    all_metadata = db.get_all_queue_metadata()

    if not active_bets and not all_metadata:
        await interaction.response.send_message(
            "Não há apostas ativas ou painéis de fila para limpar.",
            ephemeral=True
        )
        return

    # Defer a resposta porque pode demorar
    await interaction.response.defer()

    deleted_channels = 0
    cancelled_bets = 0
    deleted_panels = 0

    # Cancelar todas as apostas ativas
    for bet_id, bet in list(active_bets.items()):
        try:
            # Tenta buscar como thread
            thread = interaction.guild.get_thread(bet.channel_id)
            if not thread:
                # Tenta buscar como canal
                thread = interaction.guild.get_channel(bet.channel_id)

            if thread:
                if isinstance(thread, discord.Thread):
                    await thread.edit(archived=True, locked=True)
                else:
                    await thread.delete()
                deleted_channels += 1
        except:
            pass

        # Mover para histórico sem vencedor (cancelada)
        bet.finished_at = datetime.now().isoformat()
        db.finish_bet(bet)
        cancelled_bets += 1

    # Deletar todos os painéis de fila
    for message_id_str, metadata in list(all_metadata.items()):
        try:
            channel_id = metadata.get('channel_id')
            message_id = metadata.get('message_id')
            
            if channel_id and message_id:
                channel = interaction.guild.get_channel(channel_id)
                if channel:
                    try:
                        message = await channel.fetch_message(message_id)
                        await message.delete()
                        deleted_panels += 1
                        log(f"🗑️ Painel deletado: mensagem {message_id} no canal {channel_id}")
                    except discord.NotFound:
                        log(f"⚠️ Mensagem {message_id} não encontrada (já foi deletada)")
                    except Exception as e:
                        log(f"⚠️ Erro ao deletar mensagem {message_id}: {e}")
        except Exception as e:
            log(f"⚠️ Erro ao processar metadata {message_id_str}: {e}")

    # Limpar todas as filas e metadados
    data = db._load_data()
    data['queues'] = {}
    data['queue_timestamps'] = {}
    data['queue_metadata'] = {}
    db._save_data(data)

    # Limpar dicionário em memória
    queue_messages.clear()

    embed = discord.Embed(
        title="Sistema Desbugado",
        description="Todas as apostas ativas foram canceladas, filas limpas e painéis deletados.",
        color=EMBED_COLOR
    )
    embed.add_field(name="Apostas Canceladas", value=str(cancelled_bets), inline=True)
    embed.add_field(name="Canais Deletados", value=str(deleted_channels), inline=True)
    embed.add_field(name="Painéis Deletados", value=str(deleted_panels), inline=True)
    embed.add_field(name="Filas Limpas", value="Todas", inline=True)
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=f"{CREATOR_FOOTER} | Executado por {interaction.user.name}")

    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="setup", description="[ADMIN] Configurar cargo de mediador e canal de resultados")
@app_commands.describe(
    cargo="Cargo que poderá mediar apostas",
    canal_de_resultados="Canal onde os resultados das apostas serão enviados (opcional)"
)
async def setup(interaction: discord.Interaction, cargo: discord.Role, canal_de_resultados: discord.TextChannel = None):
    # Apenas administradores podem usar este comando
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "Apenas administradores podem usar este comando.",
            ephemeral=True
        )
        return

    # Salvar o cargo de mediador no banco de dados
    db.set_mediator_role(interaction.guild.id, cargo.id)

    # Salvar o canal de resultados se fornecido
    if canal_de_resultados:
        db.set_results_channel(interaction.guild.id, canal_de_resultados.id)

    embed = discord.Embed(
        title="Configuração Salva",
        description=f"Cargo de mediador definido como {cargo.mention}",
        color=EMBED_COLOR
    )
    embed.add_field(
        name="Permissões",
        value=f"Membros com o cargo {cargo.mention} agora podem:\n"
              "• Aceitar mediação de apostas\n"
              "• Finalizar apostas\n"
              "• Cancelar apostas\n"
              "• Criar filas com `/mostrar-fila`",
        inline=False
    )
    
    if canal_de_resultados:
        embed.add_field(
            name="Canal de Resultados",
            value=f"Os resultados das apostas serão enviados em {canal_de_resultados.mention}",
            inline=False
        )
    
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=CREATOR_FOOTER)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="ajuda", description="Ver todos os comandos disponíveis")
async def ajuda(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Bot de Apostado - Comandos",
        description="Sistema de apostas profissional",
        color=EMBED_COLOR
    )

    embed.add_field(
        name="Comandos para Jogadores",
        value=(
            "`/confirmar-pagamento` - Confirmar que enviou o pagamento\n"
            "`/minhas-apostas` - Ver suas apostas ativas\n"
            "`/historico` - Ver histórico de apostas"
        ),
        inline=False
    )

    embed.add_field(
        name="Comandos para Mediadores/Moderadores",
        value=(
            "`/mostrar-fila` - Criar mensagem com botão para entrar na fila\n"
            "`/finalizar-aposta` - Finalizar aposta e declarar vencedor\n"
            "`/cancelar-aposta` - Cancelar uma aposta\n"
            "`/desbugar-filas` - [ADMIN] Cancelar todas apostas e limpar filas"
        ),
        inline=False
    )

    embed.add_field(
        name="Comandos para Administradores",
        value=(
            "`/setup` - Configurar cargo de mediador do servidor"
        ),
        inline=False
    )
    
    # Mostra comandos do criador apenas para ele
    if is_creator(interaction.user.id):
        embed.add_field(
            name="Comandos do Criador",
            value=(
                "`/autorizar-servidor` - Autorizar servidor a usar o bot\n"
                "`/servidores` - Listar todos os servidores do bot\n"
                "`/criar-assinatura` - Criar assinatura para servidor\n"
                "`/assinatura-permanente` - Criar assinatura permanente\n"
                "`/sair` - Sair de um servidor\n"
                "`/aviso-do-dev` - Enviar aviso em canal"
            ),
            inline=False
        )

    embed.add_field(
        name="Como Funciona",
        value=(
            "1. Admins usam `/setup @cargo` para definir quem pode mediar\n"
            "2. Moderadores criam filas com `/mostrar-fila`\n"
            "3. Clique no botão 'Entrar na Fila' da mensagem\n"
            "4. Quando encontrar outro jogador, um canal privado será criado\n"
            "5. Envie o valor da aposta para o mediador\n"
            "6. Confirme com `/confirmar-pagamento`\n"
            "7. Jogue a partida\n"
            "8. O mediador declara o vencedor com `/finalizar-aposta`"
        ),
        inline=False
    )
    if interaction.guild and interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=CREATOR_FOOTER)

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ===== COMANDOS ADMINISTRATIVOS (APENAS CRIADOR) =====

@bot.tree.command(name="servidores", description="[CRIADOR] Listar todos os servidores do bot")
async def servidores(interaction: discord.Interaction):
    """Lista todos os servidores com ID e link de convite"""
    if not is_creator(interaction.user.id):
        await interaction.response.send_message("❌ Apenas o criador do bot pode usar este comando.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    embed = discord.Embed(
        title="🌐 Servidores do Bot",
        description=f"Bot está em {len(bot.guilds)} servidor(es)",
        color=EMBED_COLOR
    )
    
    for guild in bot.guilds:
        subscription = db.get_subscription(guild.id)
        status = "✅ Ativo"
        if subscription:
            if subscription.get('permanent'):
                status = "♾️ Permanente"
            elif subscription.get('expires_at'):
                from datetime import datetime
                expires = datetime.fromisoformat(subscription['expires_at'])
                status = f"⏰ Expira: {expires.strftime('%d/%m/%Y %H:%M')}"
        else:
            status = "❌ Sem assinatura"
        
        # Tenta criar um convite
        invite_link = "Sem permissão para criar convite"
        try:
            # Tenta reutilizar convites existentes
            invites = await guild.invites()
            if invites:
                invite_link = invites[0].url
            else:
                # Cria um novo convite no primeiro canal disponível
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).create_instant_invite:
                        invite = await channel.create_invite(max_age=0, max_uses=0)
                        invite_link = invite.url
                        break
        except:
            pass
        
        field_value = f"**ID:** `{guild.id}`\n**Status:** {status}\n**Convite:** {invite_link}"
        embed.add_field(name=guild.name, value=field_value, inline=False)
    
    embed.set_footer(text=CREATOR_FOOTER)
    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="criar-assinatura", description="[CRIADOR] Criar assinatura para um servidor")
async def criar_assinatura(
    interaction: discord.Interaction,
    servidor_id: str,
    duracao: str
):
    """Cria assinatura para um servidor (ex: 30d para 30 dias, 60s para 60 segundos)"""
    if not is_creator(interaction.user.id):
        await interaction.response.send_message("❌ Apenas o criador do bot pode usar este comando.", ephemeral=True)
        return
    
    # Parse do servidor ID
    try:
        guild_id = int(servidor_id)
    except ValueError:
        await interaction.response.send_message("❌ ID do servidor inválido.", ephemeral=True)
        return
    
    # Parse da duração
    duracao = duracao.lower().strip()
    duration_seconds = None
    
    if duracao.endswith('d'):
        try:
            days = int(duracao[:-1])
            duration_seconds = days * 86400
        except ValueError:
            await interaction.response.send_message("❌ Formato inválido. Use: 30d (dias) ou 60s (segundos)", ephemeral=True)
            return
    elif duracao.endswith('s'):
        try:
            duration_seconds = int(duracao[:-1])
        except ValueError:
            await interaction.response.send_message("❌ Formato inválido. Use: 30d (dias) ou 60s (segundos)", ephemeral=True)
            return
    else:
        await interaction.response.send_message("❌ Formato inválido. Use: 30d (dias) ou 60s (segundos)", ephemeral=True)
        return
    
    # Cria a assinatura
    db.create_subscription(guild_id, duration_seconds)
    
    # Calcula a data de expiração
    from datetime import datetime, timedelta
    expires_at = datetime.now() + timedelta(seconds=duration_seconds)
    
    embed = discord.Embed(
        title="✅ Assinatura Criada",
        description=f"Assinatura criada para o servidor ID: `{guild_id}`",
        color=0x00FF00
    )
    embed.add_field(name="Duração", value=duracao, inline=True)
    embed.add_field(name="Expira em", value=expires_at.strftime('%d/%m/%Y %H:%M:%S'), inline=True)
    embed.set_footer(text=CREATOR_FOOTER)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
    log(f"📝 Assinatura criada para guild {guild_id} por {duration_seconds}s")


@bot.tree.command(name="assinatura-permanente", description="[CRIADOR] Criar assinatura permanente para um servidor")
async def assinatura_permanente(
    interaction: discord.Interaction,
    servidor_id: str
):
    """Cria assinatura permanente para um servidor"""
    if not is_creator(interaction.user.id):
        await interaction.response.send_message("❌ Apenas o criador do bot pode usar este comando.", ephemeral=True)
        return
    
    # Parse do servidor ID
    try:
        guild_id = int(servidor_id)
    except ValueError:
        await interaction.response.send_message("❌ ID do servidor inválido.", ephemeral=True)
        return
    
    # Cria assinatura permanente
    db.create_subscription(guild_id, None)
    
    embed = discord.Embed(
        title="♾️ Assinatura Permanente Criada",
        description=f"Assinatura permanente criada para o servidor ID: `{guild_id}`",
        color=0x00FF00
    )
    embed.set_footer(text=CREATOR_FOOTER)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)
    log(f"♾️ Assinatura permanente criada para guild {guild_id}")


@bot.tree.command(name="sair", description="[CRIADOR] Sair de um servidor e cancelar assinatura")
async def sair(
    interaction: discord.Interaction,
    servidor_id: str
):
    """Remove o bot de um servidor e cancela a assinatura"""
    if not is_creator(interaction.user.id):
        await interaction.response.send_message("❌ Apenas o criador do bot pode usar este comando.", ephemeral=True)
        return
    
    # Parse do servidor ID
    try:
        guild_id = int(servidor_id)
    except ValueError:
        await interaction.response.send_message("❌ ID do servidor inválido.", ephemeral=True)
        return
    
    # Busca o servidor
    guild = bot.get_guild(guild_id)
    if not guild:
        await interaction.response.send_message("❌ Servidor não encontrado.", ephemeral=True)
        return
    
    guild_name = guild.name
    
    # Remove assinatura
    db.remove_subscription(guild_id)
    
    # Sai do servidor
    try:
        await guild.leave()
        
        embed = discord.Embed(
            title="👋 Saiu do Servidor",
            description=f"Bot saiu do servidor **{guild_name}** (ID: `{guild_id}`)\nAssinatura removida.",
            color=0xFF9900
        )
        embed.set_footer(text=CREATOR_FOOTER)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        log(f"👋 Bot saiu do servidor {guild_name} ({guild_id}) por comando do criador")
    except Exception as e:
        await interaction.response.send_message(f"❌ Erro ao sair do servidor: {e}", ephemeral=True)
        log(f"❌ Erro ao sair do servidor {guild_id}: {e}")


@bot.tree.command(name="autorizar-servidor", description="[CRIADOR] Autorizar um servidor para usar o bot")
@app_commands.describe(
    servidor_id="ID do servidor para autorizar",
    duracao="Duração (30d, 60s) ou deixe vazio para permanente"
)
async def autorizar_servidor(
    interaction: discord.Interaction,
    servidor_id: str,
    duracao: str = None
):
    """Autoriza um servidor a usar o bot (apenas disponível no servidor auto-autorizado)"""
    if not is_creator(interaction.user.id):
        await interaction.response.send_message("❌ Apenas o criador do bot pode usar este comando.", ephemeral=True)
        return
    
    # Permite usar no servidor auto-autorizado OU em DM
    if interaction.guild and interaction.guild.id != AUTO_AUTHORIZED_GUILD_ID:
        await interaction.response.send_message(
            f"❌ Este comando só pode ser usado no servidor autorizado ou em DM.",
            ephemeral=True
        )
        return
    
    # Parse do servidor ID
    try:
        guild_id = int(servidor_id)
    except ValueError:
        await interaction.response.send_message("❌ ID do servidor inválido.", ephemeral=True)
        return
    
    # Verifica se é o próprio servidor auto-autorizado
    if guild_id == AUTO_AUTHORIZED_GUILD_ID:
        await interaction.response.send_message("ℹ️ Este servidor já é auto-autorizado permanentemente.", ephemeral=True)
        return
    
    # Se não especificou duração, cria permanente
    if not duracao:
        db.create_subscription(guild_id, None)
        embed = discord.Embed(
            title="♾️ Servidor Autorizado Permanentemente",
            description=f"Servidor ID `{guild_id}` agora tem acesso permanente ao bot.",
            color=0x00FF00
        )
    else:
        # Parse da duração
        duracao_str = duracao.lower().strip()
        duration_seconds = None
        
        if duracao_str.endswith('d'):
            try:
                days = int(duracao_str[:-1])
                duration_seconds = days * 86400
            except ValueError:
                await interaction.response.send_message("❌ Formato inválido. Use: 30d (dias) ou 60s (segundos)", ephemeral=True)
                return
        elif duracao_str.endswith('s'):
            try:
                duration_seconds = int(duracao_str[:-1])
            except ValueError:
                await interaction.response.send_message("❌ Formato inválido. Use: 30d (dias) ou 60s (segundos)", ephemeral=True)
                return
        else:
            await interaction.response.send_message("❌ Formato inválido. Use: 30d (dias) ou 60s (segundos)", ephemeral=True)
            return
        
        db.create_subscription(guild_id, duration_seconds)
        
        from datetime import datetime, timedelta
        expires_at = datetime.now() + timedelta(seconds=duration_seconds)
        
        embed = discord.Embed(
            title="✅ Servidor Autorizado",
            description=f"Servidor ID `{guild_id}` autorizado por {duracao}",
            color=0x00FF00
        )
        embed.add_field(name="Expira em", value=expires_at.strftime('%d/%m/%Y %H:%M:%S'), inline=True)
    
    embed.set_footer(text=CREATOR_FOOTER)
    await interaction.response.send_message(embed=embed, ephemeral=True)
    log(f"🔓 Servidor {guild_id} autorizado por {interaction.user.name}")

@bot.tree.command(name="aviso-do-dev", description="[CRIADOR] Enviar mensagem em um canal específico")
async def aviso_do_dev(
    interaction: discord.Interaction,
    canal_id: str,
    mensagem: str
):
    """Envia uma mensagem em um canal específico"""
    if not is_creator(interaction.user.id):
        await interaction.response.send_message("❌ Apenas o criador do bot pode usar este comando.", ephemeral=True)
        return
    
    # Parse do canal ID
    try:
        channel_id = int(canal_id)
    except ValueError:
        await interaction.response.send_message("❌ ID do canal inválido.", ephemeral=True)
        return
    
    # Busca o canal
    channel = bot.get_channel(channel_id)
    if not channel:
        await interaction.response.send_message("❌ Canal não encontrado.", ephemeral=True)
        return
    
    if not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message("❌ O canal precisa ser um canal de texto.", ephemeral=True)
        return
    
    # Envia a mensagem
    try:
        embed = discord.Embed(
            title="📢 Aviso do Desenvolvedor",
            description=mensagem,
            color=EMBED_COLOR
        )
        embed.set_footer(text=CREATOR_FOOTER)
        
        await channel.send(embed=embed)
        
        await interaction.response.send_message(f"✅ Mensagem enviada para {channel.mention}", ephemeral=True)
        log(f"📢 Aviso do dev enviado para canal {channel.name} ({channel.id})")
    except Exception as e:
        await interaction.response.send_message(f"❌ Erro ao enviar mensagem: {e}", ephemeral=True)
        log(f"❌ Erro ao enviar aviso: {e}")


# ===== TASK PERIÓDICA PARA VERIFICAR ASSINATURAS =====

@tasks.loop(minutes=10)
async def check_expired_subscriptions():
    """Verifica assinaturas expiradas e remove o bot dos servidores"""
    try:
        log("🔍 Verificando assinaturas expiradas...")
        
        expired_guilds = db.get_expired_subscriptions()
        
        if not expired_guilds:
            log("✅ Nenhuma assinatura expirada")
            return
        
        log(f"⚠️ {len(expired_guilds)} assinatura(s) expirada(s)")
        
        for guild_id in expired_guilds:
            guild = bot.get_guild(guild_id)
            if guild:
                log(f"⏰ Assinatura expirada: {guild.name} ({guild_id})")
                
                try:
                    # Tenta notificar o servidor
                    channel = None
                    if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
                        channel = guild.system_channel
                    else:
                        for ch in guild.text_channels:
                            if ch.permissions_for(guild.me).send_messages:
                                channel = ch
                                break
                    
                    if channel:
                        embed = discord.Embed(
                            title="⏰ Assinatura Expirada",
                            description="A assinatura deste servidor expirou. O bot será removido em breve.",
                            color=0xFF9900
                        )
                        embed.add_field(
                            name="📩 Para renovar:",
                            value=(
                                "Fale diretamente comigo — [Discord DM](https://discord.com/users/1339336477661724674)\n"
                                "ou entre no meu servidor: https://discord.gg/yFhyc4RS5c"
                            ),
                            inline=False
                        )
                        embed.set_footer(text=CREATOR_FOOTER)
                        
                        await channel.send(embed=embed)
                        log(f"📨 Notificação enviada para {guild.name}")
                    
                    await asyncio.sleep(5)
                    
                    # Sai do servidor
                    await guild.leave()
                    log(f"👋 Bot saiu de {guild.name} (assinatura expirada)")
                    
                except Exception as e:
                    log(f"⚠️ Erro ao processar guild {guild_id}: {e}")
                
                # Remove a assinatura do banco
                db.remove_subscription(guild_id)
            else:
                # Servidor não encontrado, apenas remove a assinatura
                db.remove_subscription(guild_id)
                log(f"🗑️ Assinatura removida para guild {guild_id} (servidor não encontrado)")
        
        log("✅ Verificação de assinaturas concluída")
        
    except Exception as e:
        log(f"❌ Erro ao verificar assinaturas: {e}")
        logger.exception("Stacktrace:")

@check_expired_subscriptions.before_loop
async def before_check_subscriptions():
    """Aguarda o bot estar pronto antes de iniciar a task"""
    await bot.wait_until_ready()


# ===== SERVIDOR HTTP PARA HEALTHCHECK (Fly.io/Railway) =====
async def dashboard(request):
    """Endpoint principal - Dashboard com FAQ"""
    html_path = os.path.join(os.path.dirname(__file__), 'static', 'index.html')
    
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return web.Response(
            text=html_content,
            status=200,
            headers={'Content-Type': 'text/html; charset=utf-8'}
        )
    except FileNotFoundError:
        return web.Response(
            text="Dashboard not found",
            status=404
        )

async def health_check(request):
    """Endpoint de healthcheck para Fly.io/Railway"""
    bot_status = "online" if bot.is_ready() else "starting"
    return web.Response(
        text=f"Bot Status: {bot_status}\nUptime: OK", 
        status=200,
        headers={'Content-Type': 'text/plain'}
    )

async def ping(request):
    """Endpoint simples de ping"""
    return web.Response(text="pong", status=200)

async def start_web_server():
    """Inicia servidor HTTP para healthcheck e dashboard"""
    app = web.Application()
    app.router.add_get('/', dashboard)
    app.router.add_get('/health', health_check)
    app.router.add_get('/ping', ping)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    log(f"🌐 Servidor HTTP rodando em 0.0.0.0:{port}")
    log(f"   📊 Dashboard: / (página principal com FAQ)")
    log(f"   💚 Health: /health, /ping")
    return site

async def run_bot_with_webserver():
    """Roda o bot Discord junto com o servidor web"""
    token = os.getenv("DISCORD_TOKEN") or os.getenv("TOKEN") or ""
    if token == "":
        raise Exception("Por favor, adicione seu token do Discord nas variáveis de ambiente (DISCORD_TOKEN).")

    log("=" * 50)
    log("🚀 INICIANDO BOT COM SERVIDOR HTTP")
    log("=" * 50)

    # Iniciar servidor web ANTES do bot
    log("📡 Iniciando servidor HTTP...")
    web_server = await start_web_server()

    # Aguardar um pouco para o servidor estar pronto
    await asyncio.sleep(1)
    log("✅ Servidor HTTP iniciado com sucesso")

    log("🤖 Conectando bot ao Discord...")

    # Iniciar bot Discord
    try:
        await bot.start(token, reconnect=True)
    except Exception as e:
        log(f"❌ ERRO CRÍTICO ao iniciar bot: {e}")
        logger.exception("Stacktrace completo:")
        raise


# Esta função não é mais necessária - vamos usar apenas o bot principal

async def run_bot_single():
    """Roda um único bot (modo econômico)"""
    token = os.getenv("TOKEN") or os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_TOKEN_1") or ""
    if not token:
        raise Exception("Configure DISCORD_TOKEN nas variáveis de ambiente.")

    log("🤖 Modo econômico: Iniciando 1 bot...")
    await bot.start(token, reconnect=True)

def create_bot_instance():
    """Cria uma nova instância de bot com as mesmas configurações"""
    return commands.Bot(
        command_prefix="!",
        intents=intents,
        chunk_guilds_at_startup=False,
        member_cache_flags=discord.MemberCacheFlags.none(),
        max_messages=10
    )

def setup_subscription_check_task(bot_instance, bot_number):
    """Configura task de verificação de assinatura para uma instância de bot"""
    
    @tasks.loop(minutes=10)
    async def check_subscriptions_for_bot():
        """Verifica assinaturas expiradas e remove o bot dos servidores"""
        try:
            log(f"🔍 Bot #{bot_number}: Verificando assinaturas expiradas...")
            
            expired_guilds = db.get_expired_subscriptions()
            
            if not expired_guilds:
                log(f"✅ Bot #{bot_number}: Nenhuma assinatura expirada")
                return
            
            log(f"⚠️ Bot #{bot_number}: {len(expired_guilds)} assinatura(s) expirada(s)")
            
            for guild_id in expired_guilds:
                guild = bot_instance.get_guild(guild_id)
                if guild:
                    log(f"⏰ Bot #{bot_number}: Assinatura expirada em {guild.name} ({guild_id})")
                    
                    try:
                        # Tenta notificar o servidor
                        channel = None
                        if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
                            channel = guild.system_channel
                        else:
                            for ch in guild.text_channels:
                                if ch.permissions_for(guild.me).send_messages:
                                    channel = ch
                                    break
                        
                        if channel:
                            embed = discord.Embed(
                                title="⏰ Assinatura Expirada",
                                description="A assinatura deste servidor expirou. O bot será removido em breve.",
                                color=0xFF9900
                            )
                            embed.add_field(
                                name="📩 Para renovar:",
                                value=(
                                    "Fale diretamente comigo — [Discord DM](https://discord.com/users/1339336477661724674)\n"
                                    "ou entre no meu servidor: https://discord.gg/yFhyc4RS5c"
                                ),
                                inline=False
                            )
                            embed.set_footer(text=CREATOR_FOOTER)
                            
                            await channel.send(embed=embed)
                            log(f"📨 Bot #{bot_number}: Notificação enviada para {guild.name}")
                        
                        await asyncio.sleep(5)
                        
                        # Sai do servidor
                        await guild.leave()
                        log(f"👋 Bot #{bot_number}: Saiu de {guild.name} (assinatura expirada)")
                        
                    except Exception as e:
                        log(f"⚠️ Bot #{bot_number}: Erro ao processar guild {guild_id}: {e}")
                    
                    # Remove a assinatura do banco (apenas o Bot #1 faz isso para evitar conflitos)
                    if bot_number == 1:
                        db.remove_subscription(guild_id)
                else:
                    # Servidor não encontrado, apenas remove a assinatura (apenas Bot #1)
                    if bot_number == 1:
                        db.remove_subscription(guild_id)
                        log(f"🗑️ Bot #{bot_number}: Assinatura removida para guild {guild_id} (servidor não encontrado)")
            
            log(f"✅ Bot #{bot_number}: Verificação de assinaturas concluída")
            
        except Exception as e:
            log(f"❌ Bot #{bot_number}: Erro ao verificar assinaturas: {e}")
            logger.exception(f"Bot #{bot_number} Stacktrace:")
    
    @check_subscriptions_for_bot.before_loop
    async def before_check():
        """Aguarda o bot estar pronto antes de iniciar a task"""
        await bot_instance.wait_until_ready()
    
    return check_subscriptions_for_bot

async def run_single_bot_instance(bot_instance, token, bot_number, is_primary=False):
    """Inicia uma única instância de bot"""
    try:
        log(f"🤖 Bot #{bot_number}: Iniciando...")
        log(f"📋 Bot #{bot_number} Token: {token[:20]}...{token[-10:]}")
        
        if is_primary:
            log(f"👑 Bot #{bot_number} é o bot principal (com tasks de limpeza)")
        
        # Configurar task de verificação de assinatura para este bot
        subscription_task = setup_subscription_check_task(bot_instance, bot_number)
        subscription_task.start()
        log(f"🔐 Bot #{bot_number}: Task de verificação de assinaturas iniciada")
        
        await bot_instance.start(token, reconnect=True)
    except Exception as e:
        log(f"❌ Bot #{bot_number} falhou: {e}")
        logger.exception(f"Stacktrace Bot #{bot_number}:")
        raise

async def run_multiple_bots():
    """Roda múltiplos bots simultaneamente (até 3 tokens)"""
    # Coletar todos os tokens disponíveis
    tokens = []
    for i in range(1, 4):  # DISCORD_TOKEN_1, DISCORD_TOKEN_2, DISCORD_TOKEN_3
        token = os.getenv(f"DISCORD_TOKEN_{i}")
        if token:
            tokens.append((i, token))
    
    # Fallback para tokens antigos
    if not tokens:
        token = os.getenv("TOKEN") or os.getenv("DISCORD_TOKEN")
        if token:
            tokens.append((1, token))
    
    if not tokens:
        raise Exception("Configure pelo menos um token: DISCORD_TOKEN_1, DISCORD_TOKEN_2 ou DISCORD_TOKEN_3")
    
    log(f"🔢 {len(tokens)} token(s) detectado(s)")
    
    # Se tiver apenas 1 token, usar o bot principal
    if len(tokens) == 1:
        bot_num, token = tokens[0]
        log(f"🤖 Modo SINGLE BOT")
        log(f"📋 Token: {token[:20]}...{token[-10:]}")
        
        # Configurar task de verificação de assinatura
        subscription_task = setup_subscription_check_task(bot, bot_num)
        subscription_task.start()
        log(f"🔐 Bot #{bot_num}: Task de verificação de assinaturas iniciada")
        
        await bot.start(token, reconnect=True)
        return
    
    # Múltiplos tokens: criar instâncias separadas e rodar em paralelo
    log(f"🤖 Modo MÚLTIPLOS BOTS ({len(tokens)} bots)")
    log(f"💡 Cada bot terá seus próprios comandos e eventos")
    
    # Criar tarefas para cada bot
    tasks = []
    bot_instances = []
    
    for idx, (bot_num, token) in enumerate(tokens):
        is_primary = (idx == 0)
        
        if is_primary:
            # Para o primeiro token, usar o bot principal já configurado
            bot_instance = bot
            log(f"👑 Bot #{bot_num}: Usando instância principal")
        else:
            # Para tokens adicionais, criar novas instâncias de bot
            bot_instance = create_bot_instance()
            
            # Copiar a árvore de comandos do bot principal
            bot_instance.tree._copy_from(bot.tree)
            
            # Copiar todos os eventos do bot principal
            for event_name, listeners in bot.extra_events.items():
                for listener in listeners:
                    bot_instance.add_listener(listener, event_name)
            
            log(f"🆕 Bot #{bot_num}: Nova instância criada e configurada")
        
        bot_instances.append(bot_instance)
        task = run_single_bot_instance(bot_instance, token, bot_num, is_primary)
        tasks.append(task)
    
    # Rodar todos os bots em paralelo
    log(f"🚀 Iniciando {len(tasks)} bots simultaneamente...")
    log(f"✅ TODOS os bots verificam e saem de servidores sem assinatura")
    log(f"💾 Apenas o Bot #1 remove assinaturas do banco de dados")
    
    await asyncio.gather(*tasks, return_exceptions=True)

try:
    if IS_FLYIO:
        log("=" * 60)
        log("✈️  INICIANDO NO FLY.IO")
        log("=" * 60)
        log(f"📍 App: {os.getenv('FLY_APP_NAME')}")
        log(f"🌍 Region: {os.getenv('FLY_REGION', 'N/A')}")
        log(f"🔧 Alloc ID: {os.getenv('FLY_ALLOC_ID', 'N/A')}")

        async def run_flyio():
            # Iniciar servidor web primeiro
            log("📡 Iniciando servidor HTTP...")
            await start_web_server()
            await asyncio.sleep(1)
            log("✅ Servidor HTTP rodando")

            # No Fly.io, suporta múltiplos bots (até 3)
            log("🤖 Fly.io: Modo múltiplos bots")
            log("💡 Configure DISCORD_TOKEN_1, DISCORD_TOKEN_2, DISCORD_TOKEN_3")
            log("🚀 Iniciando bots Discord...")
            await run_multiple_bots()

        asyncio.run(run_flyio())

    elif IS_RAILWAY:
        log("Iniciando bot no Railway com servidor HTTP...")

        async def run_all():
            # Iniciar servidor web primeiro
            await start_web_server()
            await asyncio.sleep(1)

            # No Railway, usar apenas 1 bot por deployment
            token = os.getenv("TOKEN") or os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_TOKEN_1") or ""
            if not token:
                raise Exception("Configure DISCORD_TOKEN nas variáveis de ambiente")

            log("🤖 Railway: Modo single bot")
            
            # Configurar task de verificação de assinatura
            subscription_task = setup_subscription_check_task(bot, 1)
            subscription_task.start()
            log("🔐 Task de verificação de assinaturas iniciada")
            
            await bot.start(token, reconnect=True)

        asyncio.run(run_all())
    else:
        log("Iniciando bots no Replit/Local com servidor HTTP...")

        async def run_replit():
            # Iniciar servidor web primeiro
            await start_web_server()
            await asyncio.sleep(1)
            # No Replit, pode rodar múltiplos bots se necessário
            await run_multiple_bots()

        asyncio.run(run_replit())

except discord.HTTPException as e:
    if e.status == 429:
        log("O Discord bloqueou a conexão por excesso de requisições")
        log("Veja: https://stackoverflow.com/questions/66724687/in-discord-py-how-to-solve-the-error-for-toomanyrequests")
    else:
        raise e
except Exception as e:
    log(f"Erro ao iniciar os bots: {e}")
    if IS_RAILWAY:
        # No Railway, queremos saber exatamente o que deu errado
        import traceback
        traceback.print_exc()
        raise
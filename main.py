import os
import sys
import discord
from discord import app_commands
from discord.ext import commands
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
# Note: queue_locks_creation_lock será criado no loop de eventos

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
ACTIVE_BETS_CATEGORY = "💰 Apostas Ativas"
EMBED_COLOR = 0x5865F2
CREATOR_FOOTER = "Bot feito por SKplay. Todos os direitos reservados | Criador: <@1339336477661724674>"

# Dicionário para mapear queue_id -> (channel_id, message_id, mode, bet_value)
queue_messages = {}


class QueueButton(discord.ui.View):
    def __init__(self, mode: str, bet_value: float, mediator_fee: float, message_id: int = None):
        super().__init__(timeout=None)
        self.mode = mode
        self.bet_value = bet_value
        self.mediator_fee = mediator_fee
        self.message_id = message_id
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

            embed = discord.Embed(
                title=mode.replace('-', ' ').title(),
                color=EMBED_COLOR
            )

            embed.add_field(name="Valor", value=f"R$ {bet_value:.2f}".replace('.', ','), inline=True)
            embed.add_field(name="Fila", value=players_text if players_text != "Nenhum jogador na fila" else "Vazio", inline=True)
            if guild_icon_url:
                embed.set_thumbnail(url=guild_icon_url)
            embed.set_footer(text=CREATOR_FOOTER)

            await message.edit(embed=embed)
            log(f"✅ Mensagem da fila {queue_id} editada com sucesso")
        except Exception as e:
            log(f"❌ Erro ao atualizar mensagem da fila: {e}")

    @discord.ui.button(label='Entrar na Fila', style=discord.ButtonStyle.blurple, row=0, custom_id='persistent:join_queue')
    async def join_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id

        # Busca metadados da fila do banco de dados
        metadata = db.get_queue_metadata(interaction.message.id)
        if metadata:
            mode = metadata['mode']
            bet_value = metadata['bet_value']
            mediator_fee = metadata['mediator_fee']
            queue_id = metadata['queue_id']
        else:
            mode = self.mode
            bet_value = self.bet_value
            mediator_fee = self.mediator_fee
            queue_id = self.queue_id

        if db.is_user_in_active_bet(user_id):
            await interaction.response.send_message(
                "Você já está em uma aposta ativa. Finalize ela antes de entrar em outra fila.",
                ephemeral=True
            )
            return

        # Adquire lock para esta fila para evitar race conditions
        if queue_id not in queue_locks:
            queue_locks[queue_id] = asyncio.Lock()

        async with queue_locks[queue_id]:
            # Recarrega a fila dentro do lock
            queue = db.get_queue(queue_id)

            if user_id in queue:
                await interaction.response.send_message(
                    "Você já está nesta fila.",
                    ephemeral=True
                )
                return

            # Adiciona à fila
            db.add_to_queue(queue_id, user_id)
            queue = db.get_queue(queue_id)

        # Verifica se tem 2 jogadores para criar aposta
        if len(queue) >= 2:
                log(f"🎯 2 jogadores encontrados na fila {queue_id}! Iniciando criação de aposta...")
                log(f"💰 Valores antes de criar tópico: bet_value={bet_value} (type={type(bet_value)}), mediator_fee={mediator_fee} (type={type(mediator_fee)})")
                
                # Garante conversão para float
                bet_value = float(bet_value)
                mediator_fee = float(mediator_fee)
                log(f"💰 Valores após conversão: bet_value={bet_value}, mediator_fee={mediator_fee}")
                
                # DEFER IMEDIATAMENTE para evitar timeout (3 segundos)
                await interaction.response.defer(ephemeral=True)
                log(f"⏳ Interação deferida (evita timeout)")
                
                player1_id = queue[0]
                player2_id = queue[1]

                # Envia mensagem de confirmação (sem validar se estão no servidor)
                player1_mention = f"<@{player1_id}>"
                player2_mention = f"<@{player2_id}>"
                embed = discord.Embed(
                    title="✅ Aposta encontrada!",
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

                # Atualiza a mensagem após remover os jogadores
                try:
                    guild_icon = interaction.guild.icon.url if interaction.guild.icon else None
                    await self.update_queue_message(interaction.channel, guild_icon, interaction.message.id)
                    log(f"✅ Mensagem da fila atualizada")
                except Exception as e:
                    log(f"⚠️ Erro ao atualizar mensagem da fila: {e}")

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
                    title="✅ Entrou na fila",
                    description=f"{mode.replace('-', ' ').title()} - {len(queue)}/2",
                    color=EMBED_COLOR
                )
                if interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                embed.set_footer(text=CREATOR_FOOTER)

                await interaction.response.send_message(embed=embed, ephemeral=True)

                # Atualiza a mensagem principal
                try:
                    message = await interaction.channel.fetch_message(interaction.message.id)

                    player_names = [f"<@{uid}>" for uid in queue]
                    players_text = "\n".join(player_names) if player_names else "Vazio"

                    embed_update = discord.Embed(
                        title=mode.replace('-', ' ').title(),
                        color=EMBED_COLOR
                    )
                    embed_update.add_field(name="Valor", value=f"R$ {bet_value:.2f}".replace('.', ','), inline=True)
                    embed_update.add_field(name="Fila", value=players_text, inline=True)
                    if interaction.guild.icon:
                        embed_update.set_thumbnail(url=interaction.guild.icon.url)
                    embed_update.set_footer(text=CREATOR_FOOTER)

                    await message.edit(embed=embed_update)
                except Exception as e:
                    log(f"Erro ao atualizar mensagem da fila: {e}")

    @discord.ui.button(label='Sair da Fila', style=discord.ButtonStyle.gray, row=0, custom_id='persistent:leave_queue')
    async def leave_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id

        # Busca metadados da fila do banco de dados
        metadata = db.get_queue_metadata(interaction.message.id)
        if metadata:
            queue_id = metadata['queue_id']
        else:
            queue_id = self.queue_id

        queue = db.get_queue(queue_id)

        if user_id not in queue:
            await interaction.response.send_message(
                "Você não está nesta fila.",
                ephemeral=True
            )
            return

        db.remove_from_queue(queue_id, user_id)

        embed = discord.Embed(
            title="❌ Saiu da fila",
            color=EMBED_COLOR
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=CREATOR_FOOTER)

        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Atualiza a mensagem principal
        guild_icon = interaction.guild.icon.url if interaction.guild.icon else None
        await self.update_queue_message(interaction.channel, guild_icon, interaction.message.id)


class ConfirmPaymentButton(discord.ui.View):
    def __init__(self, bet_id: str):
        super().__init__(timeout=None)
        self.bet_id = bet_id

    @discord.ui.button(label='Confirmar Pagamento', style=discord.ButtonStyle.green, emoji='💰', custom_id='persistent:confirm_payment')
    async def confirm_payment_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        bet = db.get_active_bet(self.bet_id)

        if not bet:
            await interaction.response.send_message(
                "Esta aposta não foi encontrada.",
                ephemeral=True
            )
            return

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
                title="✅ Pagamento Confirmado",
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
                title="✅ Pagamento Confirmado",
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
                title="✅ Pagamentos Confirmados",
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


class AcceptMediationButton(discord.ui.View):
    def __init__(self, bet_id: str):
        super().__init__(timeout=None)
        self.bet_id = bet_id

    @discord.ui.button(label='Aceitar Mediação', style=discord.ButtonStyle.green, custom_id='persistent:accept_mediation')
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        bet = db.get_active_bet(self.bet_id)

        if not bet:
            await interaction.response.send_message("Aposta não encontrada.", ephemeral=True)
            return

        if bet.mediator_id != 0:
            await interaction.response.send_message("Esta aposta já tem um mediador.", ephemeral=True)
            return

        mediator_role_id = db.get_mediator_role(interaction.guild.id)
        has_mediator_role = mediator_role_id and discord.utils.get(interaction.user.roles, id=mediator_role_id) is not None

        if not has_mediator_role:
            if mediator_role_id:
                await interaction.response.send_message(
                    f"❌ Você precisa ter o cargo <@&{mediator_role_id}> para aceitar mediação.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ Este servidor ainda não configurou um cargo de mediador.\n"
                    "💡 Um administrador deve usar `/setup @cargo` para configurar.",
                    ephemeral=True
                )
            return

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
                    f"❌ Você precisa ter o cargo <@&{mediator_role_id}> para cancelar apostas.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "❌ Este servidor ainda não configurou um cargo de mediador.\n"
                    "💡 Um administrador deve usar `/setup @cargo` para configurar.",
                    ephemeral=True
                )
            return

        # Usa menções diretas (economiza chamadas API)
        embed = discord.Embed(
            title="❌ Aposta Cancelada",
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

                    # Limpa filas completamente vazias e seu metadata
                    queue = db.get_queue(queue_id)
                    if not queue:
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
                                    embed.add_field(name="Valor", value=f"R$ {bet_value:.2f}".replace('.', ','), inline=True)
                                    embed.add_field(name="Time 1", value=team1_text, inline=True)
                                    embed.add_field(name="Time 2", value=team2_text, inline=True)
                                    if channel.guild and channel.guild.icon:
                                        embed.set_thumbnail(url=channel.guild.icon.url)
                                else:
                                    queue = db.get_queue(queue_id)

                                    # Usa menções diretas (economiza API calls)
                                    players_text = "\n".join([f"<@{uid}>" for uid in queue]) if queue else "Vazio"

                                    embed = discord.Embed(
                                        title=mode.replace('-', ' ').title(),
                                        color=EMBED_COLOR
                                    )
                                    embed.add_field(name="Valor", value=f"R$ {bet_value:.2f}".replace('.', ','), inline=True)
                                    embed.add_field(name="Fila", value=players_text, inline=True)
                                    if channel.guild and channel.guild.icon:
                                        embed.set_thumbnail(url=channel.guild.icon.url)

                                await message.edit(embed=embed)
                        except Exception as e:
                            log(f"Erro ao atualizar mensagem da fila {queue_id}: {e}")

            # Aguarda 60 segundos antes de verificar novamente (economiza processamento)
            await asyncio.sleep(60)

        except Exception as e:
            log(f"Erro na limpeza de filas: {e}")
            await asyncio.sleep(60)


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
        synced = await bot.tree.sync()
        log(f'✅ {len(synced)} comandos sincronizados com sucesso')
        for cmd in synced:
            log(f'  - /{cmd.name}')
    except Exception as e:
        log(f'⚠️ Erro ao sincronizar comandos: {e}')
        logger.exception("Stacktrace:")
        # Não falha o startup por causa de erro de sync

    # Registrar views persistentes (para botões não expirarem)
    log('📋 Registrando views persistentes...')

    # Registra apenas UMA VEZ cada view persistente
    # IMPORTANTE: Não criar novas instâncias, reutilizar as mesmas
    if not hasattr(bot, '_persistent_views_registered'):
        bot.add_view(QueueButton(mode="", bet_value=0, mediator_fee=0))
        bot.add_view(ConfirmPaymentButton(bet_id=""))
        bot._persistent_views_registered = True
        log('✅ Views persistentes registradas')
    else:
        log('ℹ️ Views persistentes já estavam registradas')

    # Inicia a tarefa de limpeza automática de filas (apenas uma vez)
    if not hasattr(bot, '_cleanup_task_started'):
        bot.loop.create_task(cleanup_expired_queues())
        bot.loop.create_task(cleanup_orphaned_data_task())
        bot._cleanup_task_started = True
        log('🧹 Tarefas de limpeza iniciadas')
    else:
        log('ℹ️ Tarefas de limpeza já estavam rodando')





@bot.tree.command(name="mostrar-fila", description="[MODERADOR] Criar mensagem com botão para entrar na fila")
@app_commands.describe(
    modo="Escolha o modo de jogo",
    valor="Valor da aposta (exemplo: 5.00)",
    taxa="Taxa do mediador (exemplo: 0.50)"
)
@app_commands.choices(modo=[
    app_commands.Choice(name="1v1 Misto", value="1v1-misto"),
    app_commands.Choice(name="1v1 Mob", value="1v1-mob"),
    app_commands.Choice(name="2v2 Misto", value="2v2-misto"),
    app_commands.Choice(name="2v2 Mob", value="2v2-mob"),
])
async def mostrar_fila(interaction: discord.Interaction, modo: app_commands.Choice[str], valor: float, taxa: float):
    # Busca o cargo de mediador configurado
    mediator_role_id = db.get_mediator_role(interaction.guild.id)

    # Verifica se tem o cargo de mediador configurado
    has_mediator_role = mediator_role_id and discord.utils.get(interaction.user.roles, id=mediator_role_id) is not None

    if not has_mediator_role:
        if mediator_role_id:
            await interaction.response.send_message(
                f"❌ Você precisa ter o cargo <@&{mediator_role_id}> para usar este comando.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Este servidor ainda não configurou um cargo de mediador.\n"
                "💡 Um administrador deve usar `/setup @cargo` para configurar.",
                ephemeral=True
            )
        return

    mode = modo.value

    embed = discord.Embed(
        title=modo.name,
        color=EMBED_COLOR
    )

    embed.add_field(name="Valor", value=f"R$ {valor:.2f}".replace('.', ','), inline=True)
    embed.add_field(name="Fila", value="Vazio", inline=True)
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=CREATOR_FOOTER)

    await interaction.response.send_message(embed=embed)

    # Pega a mensagem enviada para passar o ID para o botão
    message = await interaction.original_response()
    view = QueueButton(mode, valor, taxa, message.id)

    await message.edit(embed=embed, view=view)

    # Salva os metadados da fila no banco de dados (para views persistentes)
    db.save_queue_metadata(message.id, mode, valor, taxa, interaction.channel.id)

    # Salva a informação da fila para o sistema de limpeza automática
    queue_id = f"{mode}_{message.id}"
    queue_messages[queue_id] = (interaction.channel.id, message.id, mode, valor)






async def create_bet_channel(guild: discord.Guild, mode: str, player1_id: int, player2_id: int, bet_value: float, mediator_fee: float, source_channel_id: int = None):
    log(f"🔧 create_bet_channel chamada: mode={mode}, player1={player1_id}, player2={player2_id}")
    
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
        log(f"💰 Criando objeto Bet com valores: bet_value={bet_value} ({type(bet_value)}), mediator_fee={mediator_fee} ({type(mediator_fee)})")
        
        bet = Bet(
            bet_id=bet_id,
            mode=mode,
            player1_id=player1_id,
            player2_id=player2_id,
            mediator_id=0,
            channel_id=thread.id,
            bet_value=float(bet_value),
            mediator_fee=float(mediator_fee)
        )
        db.add_active_bet(bet)
        
        log(f"✅ Bet criado e salvo no banco: bet_value={bet.bet_value}, mediator_fee={bet.mediator_fee}")
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
    
    # Formata valores corretamente (substitui ponto por vírgula)
    valor_formatado = f"R$ {float(bet_value):.2f}".replace('.', ',')
    taxa_formatada = f"R$ {float(mediator_fee):.2f}".replace('.', ',')
    
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
    bet = db.get_bet_by_channel(interaction.channel_id)

    if not bet:
        await interaction.response.send_message(
            "Este canal não é uma aposta ativa.",
            ephemeral=True
        )
        return

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
            title="✅ Pagamento Confirmado",
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
            title="✅ Pagamento Confirmado",
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
            title="✅ Pagamentos Confirmados",
            description="Partida liberada",
            color=EMBED_COLOR
        )

        await interaction.channel.send(embed=embed)


@bot.tree.command(name="finalizar-aposta", description="[MEDIADOR] Finalizar a aposta e declarar vencedor")
@app_commands.describe(vencedor="Mencione o jogador vencedor")
async def finalizar_aposta(interaction: discord.Interaction, vencedor: discord.Member):
    bet = db.get_bet_by_channel(interaction.channel_id)

    if not bet:
        await interaction.response.send_message(
            "Este tópico não é uma aposta ativa.",
            ephemeral=True
        )
        return

    # Verifica se é o mediador da aposta OU se tem o cargo de mediador
    mediator_role_id = db.get_mediator_role(interaction.guild.id)
    has_mediator_role = mediator_role_id and discord.utils.get(interaction.user.roles, id=mediator_role_id) is not None
    is_bet_mediator = interaction.user.id == bet.mediator_id

    if not is_bet_mediator and not has_mediator_role:
        await interaction.response.send_message(
            "❌ Apenas o mediador desta aposta ou membros com o cargo de mediador podem finalizá-la.",
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
        title="🏆 Vencedor",
        description=vencedor.mention,
        color=EMBED_COLOR
    )
    embed.add_field(name="Modo", value=bet.mode.replace("-", " ").title(), inline=True)
    embed.add_field(name="Perdedor", value=f"<@{loser_id}>", inline=True)
    embed.set_footer(text=CREATOR_FOOTER)

    await interaction.response.send_message(embed=embed)

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


@bot.tree.command(name="cancelar-aposta", description="[MEDIADOR] Cancelar uma aposta em andamento")
async def cancelar_aposta(interaction: discord.Interaction):
    bet = db.get_bet_by_channel(interaction.channel_id)

    if not bet:
        await interaction.response.send_message(
            "Este tópico não é uma aposta ativa.",
            ephemeral=True
        )
        return

    # Verifica se é o mediador da aposta OU se tem o cargo de mediador
    mediator_role_id = db.get_mediator_role(interaction.guild.id)
    has_mediator_role = mediator_role_id and discord.utils.get(interaction.user.roles, id=mediator_role_id) is not None
    is_bet_mediator = interaction.user.id == bet.mediator_id

    if not is_bet_mediator and not has_mediator_role:
        await interaction.response.send_message(
            "❌ Apenas o mediador desta aposta ou membros com o cargo de mediador podem cancelá-la.",
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
        title="✅ Removido de todas as filas",
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

    if not active_bets:
        await interaction.response.send_message(
            "Não há apostas ativas para cancelar.",
            ephemeral=True
        )
        return

    # Defer a resposta porque pode demorar
    await interaction.response.defer()

    deleted_channels = 0
    cancelled_bets = 0

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

    # Limpar todas as filas
    data = db._load_data()
    data['queues'] = {}
    data['queue_timestamps'] = {}
    db._save_data(data)

    embed = discord.Embed(
        title="Sistema Desbugado",
        description="Todas as apostas ativas foram canceladas e as filas limpas.",
        color=EMBED_COLOR
    )
    embed.add_field(name="Apostas Canceladas", value=str(cancelled_bets), inline=True)
    embed.add_field(name="Canais Deletados", value=str(deleted_channels), inline=True)
    embed.add_field(name="Filas Limpas", value="Todas", inline=True)
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=f"{CREATOR_FOOTER} | Executado por {interaction.user.name}")

    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="setup", description="[ADMIN] Configurar cargo de mediador para este servidor")
@app_commands.describe(cargo="Cargo que poderá mediar apostas")
async def setup(interaction: discord.Interaction, cargo: discord.Role):
    # Apenas administradores podem usar este comando
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Apenas administradores podem usar este comando.",
            ephemeral=True
        )
        return

    # Salvar o cargo de mediador no banco de dados
    db.set_mediator_role(interaction.guild.id, cargo.id)

    embed = discord.Embed(
        title="✅ Configuração Salva",
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
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=CREATOR_FOOTER)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="ajuda", description="Ver todos os comandos disponíveis")
async def ajuda(interaction: discord.Interaction):
    embed = discord.Embed(
        title="NZ Apostado - Comandos",
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
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=CREATOR_FOOTER)

    await interaction.response.send_message(embed=embed)


# ===== SERVIDOR HTTP PARA HEALTHCHECK (Fly.io/Railway) =====
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
    """Inicia servidor HTTP para healthcheck"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    app.router.add_get('/ping', ping)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

    log(f"🌐 Servidor HTTP rodando em 0.0.0.0:{port}")
    log(f"   Endpoints: /, /health, /ping")
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


def create_bot_instance(bot_number: int):
    """Cria uma nova instância do bot com todos os comandos e eventos"""
    # Configuração de intents
    bot_intents = discord.Intents(
        guilds=True,
        guild_messages=True,
        members=True,
        message_content=True
    )
    bot_intents.presences = False
    bot_intents.typing = False
    bot_intents.voice_states = False
    bot_intents.integrations = False
    bot_intents.webhooks = False
    bot_intents.invites = False
    bot_intents.emojis_and_stickers = False
    bot_intents.bans = False
    bot_intents.dm_messages = False
    bot_intents.dm_reactions = False
    bot_intents.dm_typing = False
    bot_intents.guild_reactions = False
    bot_intents.guild_typing = False
    bot_intents.moderation = False

    new_bot = commands.Bot(
        command_prefix="!",
        intents=bot_intents,
        chunk_guilds_at_startup=False,
        member_cache_flags=discord.MemberCacheFlags.none(),
        max_messages=10
    )

    # Criar função de limpeza específica para esta instância do bot
    async def cleanup_for_this_bot():
        """Tarefa em background que remove jogadores que ficaram muito tempo na fila"""
        await new_bot.wait_until_ready()
        log(f"🧹 Iniciando sistema de limpeza automática de filas para Bot #{bot_number}")

        while not new_bot.is_closed():
            try:
                expired_players = db.get_expired_queue_players(timeout_minutes=5)

                if expired_players:
                    log(f"🧹 [Bot #{bot_number}] Encontrados jogadores expirados em {len(expired_players)} filas")

                    for queue_id, user_ids in expired_players.items():
                        for user_id in user_ids:
                            db.remove_from_queue(queue_id, user_id)
                            log(f"⏱️ [Bot #{bot_number}] Removido usuário {user_id} da fila {queue_id} (timeout)")

                        if queue_id in queue_messages:
                            channel_id, message_id, mode, bet_value = queue_messages[queue_id]
                            try:
                                channel = new_bot.get_channel(channel_id)
                                if channel:
                                    message = await channel.fetch_message(message_id)
                                    queue = db.get_queue(queue_id)

                                    player_names = [f"<@{uid}>" for uid in queue]
                                    players_text = "\n".join(player_names) if player_names else "Vazio"

                                    embed = discord.Embed(
                                        title=mode.replace('-', ' ').title(),
                                        color=EMBED_COLOR
                                    )
                                    embed.add_field(name="Valor", value=f"R$ {bet_value:.2f}".replace('.', ','), inline=True)
                                    embed.add_field(name="Fila", value=players_text, inline=True)
                                    if channel.guild.icon:
                                        embed.set_thumbnail(url=channel.guild.icon.url)
                                    await message.edit(embed=embed)
                            except Exception as e:
                                log(f"Erro ao atualizar mensagem da fila {queue_id}: {e}")

                await asyncio.sleep(60)

            except Exception as e:
                log(f"Erro na limpeza de filas [Bot #{bot_number}]: {e}")
                await asyncio.sleep(60)

    # Registrar evento on_ready
    @new_bot.event
    async def on_ready():
        log("=" * 50)
        log(f"✅ BOT #{bot_number} CONECTADO AO DISCORD!")
        log("=" * 50)
        log(f'👤 Usuário: {new_bot.user}')
        log(f'📛 Nome: {new_bot.user.name}')
        log(f'🆔 ID: {new_bot.user.id}')
        log(f'🌐 Servidores: {len(new_bot.guilds)}')
        
        try:
            log(f"🔄 Sincronizando comandos do Bot #{bot_number}...")
            synced = await new_bot.tree.sync()
            log(f'✅ Bot #{bot_number}: {len(synced)} comandos sincronizados')
        except Exception as e:
            log(f'⚠️ Erro ao sincronizar comandos do Bot #{bot_number}: {e}')

        # Registrar views persistentes
        log(f'📋 Registrando views persistentes para Bot #{bot_number}...')
        new_bot.add_view(QueueButton(mode="", bet_value=0, mediator_fee=0))
        new_bot.add_view(ConfirmPaymentButton(bet_id=""))
        log(f'✅ Views persistentes registradas para Bot #{bot_number}')

        # Inicia a tarefa de limpeza automática de filas para ESTE bot
        new_bot.loop.create_task(cleanup_for_this_bot())

    # Copiar todos os comandos da árvore do bot original
    for command in bot.tree.get_commands():
        new_bot.tree.add_command(command)

    return new_bot

async def run_bot_single():
    """Roda um único bot (modo econômico)"""
    token = os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_TOKEN_1") or ""
    if not token:
        raise Exception("Configure DISCORD_TOKEN nas variáveis de ambiente.")

    log("🤖 Modo econômico: Iniciando 1 bot...")
    await bot.start(token, reconnect=True)

async def run_multiple_bots():
    """Roda múltiplos bots simultaneamente com tokens diferentes na MESMA máquina"""
    # Pegar os 3 tokens do ambiente
    token1 = os.getenv("DISCORD_TOKEN_1") or os.getenv("DISCORD_TOKEN") or ""
    token2 = os.getenv("DISCORD_TOKEN_2") or ""
    token3 = os.getenv("DISCORD_TOKEN_3") or ""

    tokens = [t for t in [token1, token2, token3] if t]

    if not tokens:
        raise Exception("Configure pelo menos DISCORD_TOKEN_1 nas variáveis de ambiente.")

    # Limita a 3 bots para economizar recursos
    if len(tokens) > 3:
        log("⚠️ AVISO: Mais de 3 tokens configurados. Limitando a 3 bots para economizar recursos.")
        tokens = tokens[:3]

    log(f"🤖 Modo múltiplos bots: Iniciando {len(tokens)} bot(s)...")
    log(f"📋 Tokens encontrados:")
    for i, token in enumerate(tokens, 1):
        log(f"  {i}. DISCORD_TOKEN_{i}: {token[:20]}...{token[-10:]}")
    
    if len(tokens) > 1:
        log("💡 Múltiplos bots rodando na MESMA máquina (Fly.io)")

    # Criar uma instância de bot para cada token
    bot_instances = []
    tasks = []

    for i, token in enumerate(tokens, 1):
        log(f"🚀 Iniciando bot #{i}...")
        new_bot = create_bot_instance(bot_number=i)
        bot_instances.append(new_bot)
        
        # Cria task de inicialização do bot
        task = asyncio.create_task(new_bot.start(token, reconnect=True))
        tasks.append(task)
        
        # Pequeno delay entre inicializações para evitar rate limit
        if i < len(tokens):
            await asyncio.sleep(2)

    # Rodar todos os bots simultaneamente até todos terminarem
    log(f"✅ Todos os {len(tokens)} bots foram iniciados e rodam na mesma máquina")
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
            token = os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_TOKEN_1") or ""
            if not token:
                raise Exception("Configure DISCORD_TOKEN nas variáveis de ambiente")
            
            log("🤖 Railway: Modo single bot")
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
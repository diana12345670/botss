import os
import sys
import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
import asyncio
from datetime import datetime
from typing import Optional
from models.bet import Bet
from utils.database import Database
from aiohttp import web

# Forçar logs para stdout sem buffer (ESSENCIAL para Railway)
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

# Função para logging com flush automático (necessário para Railway)
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
IS_RENDER = os.getenv("RENDER") is not None or os.getenv("RENDER_SERVICE_NAME") is not None

if IS_FLYIO:
    log("✈️ Detectado ambiente Railway")
elif IS_RAILWAY:
    log("🚂 Detectado ambiente Railway")
elif IS_RENDER:
    log("🎨 Detectado ambiente Render")
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
CREATOR_FOOTER = "StormBet - Bot feito por SKplay. Todos os direitos reservados | Criador: <@1339336477661724674>"
CREATOR_ID = 1339336477661724674
AUTO_AUTHORIZED_GUILD_ID = 1438184380395687978  # Servidor auto-autorizado

# Dicionário para mapear queue_id -> (channel_id, message_id, mode, bet_value)
queue_messages = {}

def is_2v2_mode(mode: str) -> bool:
    return isinstance(mode, str) and mode.startswith("2v2")

def split_teams_from_queue(mode: str, queue: list[int]) -> tuple[list[int], list[int]]:
    if not is_2v2_mode(mode):
        return queue[:1], queue[1:2]
    return queue[:2], queue[2:4]

def teams_full(mode: str, queue: list[int]) -> bool:
    return len(queue) >= (4 if is_2v2_mode(mode) else 2)

def render_team_mentions(user_ids: list[int]) -> str:
    if not user_ids:
        return "Vazio"
    return "\n".join([f"<@{uid}>" for uid in user_ids])

def queue_embed_fields_for_mode(mode: str, queue: list[int]) -> dict:
    if is_2v2_mode(mode):
        t1, t2 = split_teams_from_queue(mode, queue)
        return {
            "team1": ("Time 1", f"{len(t1)}/2\n{render_team_mentions(t1)}"),
            "team2": ("Time 2", f"{len(t2)}/2\n{render_team_mentions(t2)}"),
        }
    return {
        "queue": ("Fila", render_team_mentions(queue) if queue else "Vazio")
    }

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

    # 🔧 CRIAR CONVITE **ANTES** DE SAIR DO SERVIDOR
    invite_link = "Sem permissão para criar convite"
    try:
        # Tenta reutilizar convites existentes primeiro
        invites = await guild.invites()
        if invites:
            invite_link = invites[0].url
            log(f"✅ Convite reutilizado: {invite_link}")
        else:
            # Tenta criar convite - busca o melhor canal possível
            channels_to_try = [
                guild.system_channel,  # Canal de sistema primeiro
                *guild.text_channels   # Depois tenta outros canais
            ]

            for channel in channels_to_try:
                if not channel:
                    continue
                try:
                    # Tenta criar o convite direto (admin tem permissão)
                    invite = await channel.create_invite(
                        max_age=0,      # Nunca expira
                        max_uses=0,     # Usos ilimitados
                        unique=False    # Reutiliza se já existir
                    )
                    invite_link = invite.url
                    log(f"✅ Convite criado: {invite_link}")
                    break
                except discord.Forbidden:
                    continue  # Tenta próximo canal
                except Exception as e:
                    log(f"⚠️ Erro ao criar convite no canal {channel.name}: {e}")
                    continue  # Tenta próximo canal
    except discord.Forbidden:
        invite_link = "Bot sem permissão 'Criar Convite'"
        log(f"⚠️ {invite_link}")
    except Exception as e:
        invite_link = f"Erro ao criar convite: {str(e)[:50]}"
        log(f"⚠️ Erro ao criar convite: {e}")

    # Notifica o criador via DM sobre servidor não autorizado
    try:
        creator = await bot.fetch_user(CREATOR_ID)

        embed = discord.Embed(
            title="⚠️ Bot Adicionado a Servidor Não Autorizado",
            description=f"O bot foi adicionado a um servidor sem assinatura e saiu automaticamente",
            color=0xFF9900
        )
        embed.add_field(name="Servidor", value=f"{guild.name}", inline=False)
        embed.add_field(name="ID", value=f"`{guild.id}`", inline=True)
        embed.add_field(name="Membros", value=f"{guild.member_count}", inline=True)
        embed.add_field(name="Link do Servidor", value=invite_link, inline=False)
        embed.set_footer(text=CREATOR_FOOTER)

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        await creator.send(embed=embed)
        log(f"📨 DM enviada ao criador sobre servidor não autorizado: {guild.name}")
    except Exception as e:
        log(f"⚠️ Erro ao enviar DM ao criador: {e}")

    # Aguarda um pouco antes de sair
    await asyncio.sleep(3)

    try:
        # Verifica se ainda está no servidor antes de tentar sair
        if bot.get_guild(guild.id):
            await guild.leave()
            log(f"👋 Bot saiu do servidor {guild.name} ({guild.id})")
        else:
            log(f"ℹ️ Bot já não está mais no servidor {guild.name} ({guild.id})")
    except discord.HTTPException as e:
        if e.code == 10004:  # Unknown Guild
            log(f"ℹ️ Servidor {guild.name} não existe mais (já saiu ou foi excluído)")
        else:
            log(f"⚠️ Erro ao sair do servidor: {e}")
    except Exception as e:
        log(f"⚠️ Erro inesperado ao sair do servidor: {e}")

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
                valor_formatado = f"$ {bet_value:.2f}"
                moeda_nome = "Dinheiro"

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
        except discord.NotFound:
            log(f"⚠️ Mensagem da fila {queue_id} não encontrada - ignorando atualização")
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
            # Se não encontrou metadados, pode ser problema temporário ou configuração incompleta
            log(f"❌ ERRO: Metadados não encontrados para mensagem {interaction.message.id}")
            log(f"📋 Metadados disponíveis no banco: {list(db.get_all_queue_metadata().keys())}")
            await interaction.followup.send(
                "⚠️ **Erro ao acessar esta fila**\n\n"
                "Os dados desta fila não foram encontrados. Isso pode acontecer se:\n"
                "• O painel é muito antigo e foi criado antes da atualização\n"
                "• Houve uma reinicialização recente do bot\n\n"
                "**Solução:** Peça ao mediador para criar um novo painel com `/mostrar-fila` ou `/preset-filas`.\n"
                "Os novos painéis funcionarão indefinidamente sem problemas! ✅",
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

                # VALIDAÇÃO CRÍTICA: Verifica se o painel ainda existe ANTES de remover jogadores
                try:
                    message = await interaction.channel.fetch_message(interaction.message.id)
                    log(f"✅ Painel ainda existe, prosseguindo com criação da aposta")
                except discord.NotFound:
                    log(f"❌ PAINEL FOI DELETADO! Cancelando criação de aposta")
                    await interaction.followup.send(
                        "⚠️ O painel foi deletado. A criação da aposta foi cancelada.",
                        ephemeral=True
                    )
                    return
                except Exception as e:
                    log(f"⚠️ Erro ao verificar painel: {e}")
                    await interaction.followup.send(
                        "⚠️ Erro ao verificar painel. Tente novamente.",
                        ephemeral=True
                    )
                    return

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

                    log(f"📝 Texto a ser exibido no painel: {players_text}")

                    # Formata valor baseado no tipo de moeda
                    if currency_type == "sonhos":
                        valor_formatado = format_sonhos(bet_value)
                        moeda_nome = "Sonhos"
                    else:
                        valor_formatado = f"$ {bet_value:.2f}"
                        moeda_nome = "Dinheiro"

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
                except discord.NotFound:
                    log(f"⚠️ Mensagem do painel foi deletada - limpando fila {queue_id}")
                    # Mensagem foi deletada - limpa a fila e metadados
                    db.remove_from_queue(queue_id, player1_id)
                    db.remove_from_queue(queue_id, player2_id)
                    if queue_id in queue_messages:
                        del queue_messages[queue_id]
                except Exception as e:
                    log(f"❌ Erro ao atualizar mensagem da fila: {e}")
                    logger.exception("Stacktrace:")


                # VALIDAÇÃO FINAL: Verifica novamente antes de criar tópico
                try:
                    await interaction.channel.fetch_message(interaction.message.id)
                except discord.NotFound:
                    log(f"❌ Painel deletado durante atualização! Retornando jogadores à fila")
                    db.add_to_queue(queue_id, player1_id)
                    db.add_to_queue(queue_id, player2_id)
                    return

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
                        valor_formatado = f"$ {bet_value:.2f}"
                        moeda_nome = "Dinheiro"

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
                except discord.NotFound:
                    log(f"⚠️ Mensagem do painel foi deletada - limpando fila {queue_id}")
                    # Mensagem foi deletada - limpa a fila e metadados
                    db.remove_from_queue(queue_id, user_id)
                    if queue_id in queue_messages:
                        del queue_messages[queue_id]
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
                valor_formatado = f"$ {bet_value:.2f}"
                moeda_nome = "Dinheiro"

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
        except discord.NotFound:
            log(f"⚠️ Mensagem do painel foi deletada - limpando fila {queue_id}")
            # Mensagem foi deletada - limpa a fila e metadados
            db.remove_from_queue(queue_id, user_id)
            if queue_id in queue_messages:
                del queue_messages[queue_id]
        except Exception as e:
            log(f"❌ Erro ao atualizar painel: {e}")
            logger.exception("Stacktrace:")


class TeamQueueButton(discord.ui.View):
    def __init__(self, mode: str, bet_value: float, mediator_fee: float, message_id: int = None, currency_type: str = "sonhos"):
        super().__init__(timeout=None)
        self.mode = mode
        self.bet_value = bet_value
        self.mediator_fee = mediator_fee
        self.message_id = message_id
        self.currency_type = currency_type
        self.queue_id = f"{mode}_{message_id}" if message_id else ""

    def _team_queue_ids(self, queue_id: str) -> tuple[str, str]:
        return f"{queue_id}_team1", f"{queue_id}_team2"

    async def _update_panel(self, interaction: discord.Interaction, mode: str, bet_value: float, currency_type: str, queue_id: str):
        team1_qid, team2_qid = self._team_queue_ids(queue_id)
        team1 = db.get_queue(team1_qid)
        team2 = db.get_queue(team2_qid)

        if currency_type == "sonhos":
            valor_formatado = format_sonhos(bet_value)
            moeda_nome = "Sonhos"
        else:
            valor_formatado = f"$ {bet_value:.2f}"
            moeda_nome = "Dinheiro"

        embed_update = discord.Embed(
            title=mode.replace('-', ' ').title(),
            color=EMBED_COLOR
        )
        embed_update.add_field(name="Valor", value=valor_formatado, inline=True)
        embed_update.add_field(name="Moeda", value=moeda_nome, inline=True)
        embed_update.add_field(name="Time 1", value=f"{len(team1)}/2\n{render_team_mentions(team1)}", inline=True)
        embed_update.add_field(name="Time 2", value=f"{len(team2)}/2\n{render_team_mentions(team2)}", inline=True)
        if interaction.guild.icon:
            embed_update.set_thumbnail(url=interaction.guild.icon.url)
        embed_update.set_footer(text=CREATOR_FOOTER)

        try:
            message = await interaction.channel.fetch_message(interaction.message.id)
            await message.edit(embed=embed_update)
        except Exception as e:
            log(f"❌ Erro ao atualizar painel 2v2: {e}")

    async def _load_metadata(self, interaction: discord.Interaction) -> Optional[dict]:
        try:
            return db.get_queue_metadata(interaction.message.id)
        except Exception:
            return None

    async def _ensure_lock(self, queue_id: str):
        if queue_id not in queue_locks:
            async with queue_locks_creation_lock:
                if queue_id not in queue_locks:
                    queue_locks[queue_id] = asyncio.Lock()

    async def _try_create_bet_if_full(self, interaction: discord.Interaction, mode: str, bet_value: float, mediator_fee: float, currency_type: str, queue_id: str):
        team1_qid, team2_qid = self._team_queue_ids(queue_id)

        team1 = db.get_queue(team1_qid)
        team2 = db.get_queue(team2_qid)
        if len(team1) < 2 or len(team2) < 2:
            return

        # Limpa as filas antes de criar aposta (evita corrida/duplicação)
        db.set_queue(team1_qid, [])
        db.set_queue(team2_qid, [])

        await self._update_panel(interaction, mode, bet_value, currency_type, queue_id)

        await create_bet_channel(
            interaction.guild,
            mode,
            team1[0],
            team2[0],
            float(bet_value),
            float(mediator_fee),
            interaction.channel_id,
            team1_ids=team1,
            team2_ids=team2,
            currency_type=currency_type,
        )

    @discord.ui.button(label='Entrar no Time 1', style=discord.ButtonStyle.blurple, row=0, custom_id='persistent:join_team1')
    async def join_team1_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        metadata = await self._load_metadata(interaction)
        if not metadata:
            await interaction.followup.send("⚠️ Dados da fila não encontrados. Recrie o painel.", ephemeral=True)
            return

        mode = metadata['mode']
        bet_value = float(metadata['bet_value'])
        mediator_fee = float(metadata['mediator_fee'])

        queue_id = metadata['queue_id']
        currency_type = metadata.get('currency_type', 'sonhos')

        user_id = interaction.user.id
        if db.is_user_in_active_bet(user_id):
            await interaction.followup.send("Você já está em uma aposta ativa.", ephemeral=True)
            return

        team1_qid, team2_qid = self._team_queue_ids(queue_id)
        await self._ensure_lock(queue_id)

        async with queue_locks[queue_id]:
            team1 = db.get_queue(team1_qid)
            team2 = db.get_queue(team2_qid)

            if user_id in team1 or user_id in team2:
                await interaction.followup.send("Você já está nesta fila.", ephemeral=True)
                return

            if len(team1) >= 2:
                await interaction.followup.send("Time 1 está cheio.", ephemeral=True)
                return

            db.add_to_queue(team1_qid, user_id)

        await self._update_panel(interaction, mode, bet_value, currency_type, queue_id)
        await interaction.followup.send("Você entrou no Time 1.", ephemeral=True)
        await self._try_create_bet_if_full(interaction, mode, bet_value, mediator_fee, currency_type, queue_id)

    @discord.ui.button(label='Entrar no Time 2', style=discord.ButtonStyle.blurple, row=0, custom_id='persistent:join_team2')
    async def join_team2_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        metadata = await self._load_metadata(interaction)
        if not metadata:
            await interaction.followup.send("⚠️ Dados da fila não encontrados. Recrie o painel.", ephemeral=True)
            return

        mode = metadata['mode']
        bet_value = float(metadata['bet_value'])
        mediator_fee = float(metadata['mediator_fee'])

        queue_id = metadata['queue_id']
        currency_type = metadata.get('currency_type', 'sonhos')

        user_id = interaction.user.id
        if db.is_user_in_active_bet(user_id):
            await interaction.followup.send("Você já está em uma aposta ativa.", ephemeral=True)
            return

        team1_qid, team2_qid = self._team_queue_ids(queue_id)
        await self._ensure_lock(queue_id)

        async with queue_locks[queue_id]:
            team1 = db.get_queue(team1_qid)
            team2 = db.get_queue(team2_qid)

            if user_id in team1 or user_id in team2:
                await interaction.followup.send("Você já está nesta fila.", ephemeral=True)
                return

            if len(team2) >= 2:
                await interaction.followup.send("Time 2 está cheio.", ephemeral=True)
                return

            db.add_to_queue(team2_qid, user_id)

        await self._update_panel(interaction, mode, bet_value, currency_type, queue_id)
        await interaction.followup.send("Você entrou no Time 2.", ephemeral=True)
        await self._try_create_bet_if_full(interaction, mode, bet_value, mediator_fee, currency_type, queue_id)

    @discord.ui.button(label='Sair', style=discord.ButtonStyle.gray, row=0, custom_id='persistent:leave_team_queue')
    async def leave_team_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        metadata = await self._load_metadata(interaction)
        if not metadata:
            await interaction.followup.send("⚠️ Dados da fila não encontrados. Recrie o painel.", ephemeral=True)
            return

        mode = metadata['mode']
        bet_value = float(metadata['bet_value'])
        queue_id = metadata['queue_id']
        currency_type = metadata.get('currency_type', 'sonhos')
        user_id = interaction.user.id

        team1_qid, team2_qid = self._team_queue_ids(queue_id)
        await self._ensure_lock(queue_id)

        async with queue_locks[queue_id]:
            if user_id in db.get_queue(team1_qid):
                db.remove_from_queue(team1_qid, user_id)
            elif user_id in db.get_queue(team2_qid):
                db.remove_from_queue(team2_qid, user_id)
            else:
                await interaction.followup.send("Você não está nesta fila.", ephemeral=True)
                return

        await self._update_panel(interaction, mode, bet_value, currency_type, queue_id)
        await interaction.followup.send("Você saiu da fila.", ephemeral=True)


class Unified1v1PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _load_panel(self, interaction: discord.Interaction) -> Optional[dict]:
        try:
            return db.get_panel_metadata(interaction.message.id)
        except Exception:
            return None

    def _queue_ids(self, message_id: int) -> tuple[str, str]:
        return f"1v1-mob_{message_id}", f"1v1-misto_{message_id}"

    async def _ensure_lock(self, queue_id: str):
        if queue_id not in queue_locks:
            async with queue_locks_creation_lock:
                if queue_id not in queue_locks:
                    queue_locks[queue_id] = asyncio.Lock()

    async def _update_panel(self, interaction: discord.Interaction, bet_value: float, currency_type: str):
        mob_qid, misto_qid = self._queue_ids(interaction.message.id)
        mob_queue = db.get_queue(mob_qid)
        misto_queue = db.get_queue(misto_qid)

        if currency_type == "sonhos":
            valor_formatado = format_sonhos(bet_value)
            moeda_nome = "Sonhos"
        else:
            valor_formatado = f"$ {bet_value:.2f}"
            moeda_nome = "Dinheiro"

        embed_update = discord.Embed(title="Painel 1v1", color=EMBED_COLOR)
        embed_update.add_field(name="Valor", value=valor_formatado, inline=True)
        embed_update.add_field(name="Moeda", value=moeda_nome, inline=True)
        embed_update.add_field(name="📱 1v1 MOB", value=f"{len(mob_queue)}/2\n{render_team_mentions(mob_queue)}", inline=True)
        embed_update.add_field(name="💻 1v1 MISTO", value=f"{len(misto_queue)}/2\n{render_team_mentions(misto_queue)}", inline=True)
        if interaction.guild and interaction.guild.icon:
            embed_update.set_thumbnail(url=interaction.guild.icon.url)
        embed_update.set_footer(text=CREATOR_FOOTER)

        try:
            message = await interaction.channel.fetch_message(interaction.message.id)
            await message.edit(embed=embed_update)
        except Exception as e:
            log(f"❌ Erro ao atualizar painel 1v1 unificado: {e}")

    async def _try_create_bet_if_ready(self, interaction: discord.Interaction, mode: str, queue_id: str, bet_value: float, mediator_fee: float):
        queue = db.get_queue(queue_id)
        if len(queue) < 2:
            return

        player1_id = queue[0]
        player2_id = queue[1]

        db.remove_from_queue(queue_id, player1_id)
        db.remove_from_queue(queue_id, player2_id)

        meta = db.get_panel_metadata(interaction.message.id) or {}
        currency_type = meta.get('currency_type', 'sonhos')
        await self._update_panel(interaction, bet_value, currency_type)

        await create_bet_channel(
            interaction.guild,
            mode,
            player1_id,
            player2_id,
            float(bet_value),
            float(mediator_fee),
            interaction.channel_id,
            currency_type=currency_type,
        )

    @discord.ui.button(label='📱 1v1 MOB', style=discord.ButtonStyle.blurple, row=0, custom_id='persistent:panel_1v1_mob')
    async def join_1v1_mob(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        meta = await self._load_panel(interaction)
        if not meta:
            await interaction.followup.send("⚠️ Dados do painel não encontrados. Recrie o painel.", ephemeral=True)
            return

        user_id = interaction.user.id
        if db.is_user_in_active_bet(user_id):
            await interaction.followup.send("Você já está em uma aposta ativa.", ephemeral=True)
            return

        mob_qid, misto_qid = self._queue_ids(interaction.message.id)
        await self._ensure_lock(mob_qid)

        async with queue_locks[mob_qid]:
            mob_queue = db.get_queue(mob_qid)
            misto_queue = db.get_queue(misto_qid)
            if user_id in mob_queue or user_id in misto_queue:
                await interaction.followup.send("Você já está em uma fila deste painel.", ephemeral=True)
                return
            db.add_to_queue(mob_qid, user_id)

        meta = db.get_panel_metadata(interaction.message.id) or {}
        currency_type = meta.get('currency_type', 'sonhos')
        await self._update_panel(interaction, float(meta['bet_value']), currency_type)
        await interaction.followup.send("Você entrou na fila 📱 1v1 MOB.", ephemeral=True)
        await self._try_create_bet_if_ready(interaction, "1v1-mob", mob_qid, float(meta['bet_value']), float(meta['mediator_fee']))

    @discord.ui.button(label='💻 1v1 MISTO', style=discord.ButtonStyle.blurple, row=0, custom_id='persistent:panel_1v1_misto')
    async def join_1v1_misto(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        meta = await self._load_panel(interaction)
        if not meta:
            await interaction.followup.send("⚠️ Dados do painel não encontrados. Recrie o painel.", ephemeral=True)
            return

        user_id = interaction.user.id
        if db.is_user_in_active_bet(user_id):
            await interaction.followup.send("Você já está em uma aposta ativa.", ephemeral=True)
            return

        mob_qid, misto_qid = self._queue_ids(interaction.message.id)
        await self._ensure_lock(misto_qid)

        async with queue_locks[misto_qid]:
            mob_queue = db.get_queue(mob_qid)
            misto_queue = db.get_queue(misto_qid)
            if user_id in mob_queue or user_id in misto_queue:
                await interaction.followup.send("Você já está em uma fila deste painel.", ephemeral=True)
                return
            db.add_to_queue(misto_qid, user_id)

        meta = db.get_panel_metadata(interaction.message.id) or {}
        currency_type = meta.get('currency_type', 'sonhos')
        await self._update_panel(interaction, float(meta['bet_value']), currency_type)
        await interaction.followup.send("Você entrou na fila 💻 1v1 MISTO.", ephemeral=True)
        await self._try_create_bet_if_ready(interaction, "1v1-misto", misto_qid, float(meta['bet_value']), float(meta['mediator_fee']))

    @discord.ui.button(label='🚪 Sair da fila', style=discord.ButtonStyle.gray, row=1, custom_id='persistent:panel_1v1_leave')
    async def leave_panel_1v1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        meta = await self._load_panel(interaction)
        if not meta:
            await interaction.followup.send("⚠️ Dados do painel não encontrados. Recrie o painel.", ephemeral=True)
            return

        user_id = interaction.user.id
        mob_qid, misto_qid = self._queue_ids(interaction.message.id)

        removed = False

        await self._ensure_lock(mob_qid)
        await self._ensure_lock(misto_qid)

        async with queue_locks[mob_qid]:
            if user_id in db.get_queue(mob_qid):
                db.remove_from_queue(mob_qid, user_id)
                removed = True

        async with queue_locks[misto_qid]:
            if user_id in db.get_queue(misto_qid):
                db.remove_from_queue(misto_qid, user_id)
                removed = True

        meta = db.get_panel_metadata(interaction.message.id) or {}
        currency_type = meta.get('currency_type', 'sonhos')
        await self._update_panel(interaction, float(meta['bet_value']), currency_type)
        await interaction.followup.send("Você saiu da fila." if removed else "Você não está em nenhuma fila deste painel.", ephemeral=True)


class Unified2v2PanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _load_panel(self, interaction: discord.Interaction) -> Optional[dict]:
        try:
            return db.get_panel_metadata(interaction.message.id)
        except Exception:
            return None

    def _base_qid(self, mode: str, message_id: int) -> str:
        return f"{mode}_{message_id}"

    def _team_qids(self, base_qid: str) -> tuple[str, str]:
        return f"{base_qid}_team1", f"{base_qid}_team2"

    async def _ensure_lock(self, queue_id: str):
        if queue_id not in queue_locks:
            async with queue_locks_creation_lock:
                if queue_id not in queue_locks:
                    queue_locks[queue_id] = asyncio.Lock()

    def _all_team_qids(self, message_id: int) -> list[str]:
        mob_base = self._base_qid("2v2-mob", message_id)
        misto_base = self._base_qid("2v2-misto", message_id)
        mob_t1, mob_t2 = self._team_qids(mob_base)
        misto_t1, misto_t2 = self._team_qids(misto_base)
        return [mob_t1, mob_t2, misto_t1, misto_t2]

    async def _update_panel(self, interaction: discord.Interaction, bet_value: float, currency_type: str):
        message_id = interaction.message.id

        mob_base = self._base_qid("2v2-mob", message_id)
        misto_base = self._base_qid("2v2-misto", message_id)
        mob_t1, mob_t2 = self._team_qids(mob_base)
        misto_t1, misto_t2 = self._team_qids(misto_base)

        mob1 = db.get_queue(mob_t1)
        mob2 = db.get_queue(mob_t2)
        misto1 = db.get_queue(misto_t1)
        misto2 = db.get_queue(misto_t2)

        if currency_type == "sonhos":
            valor_formatado = format_sonhos(bet_value)
            moeda_nome = "Sonhos"
        else:
            valor_formatado = f"$ {bet_value:.2f}"
            moeda_nome = "Dinheiro"

        embed_update = discord.Embed(title="Painel 2v2", color=EMBED_COLOR)
        embed_update.add_field(name="Valor", value=valor_formatado, inline=True)
        embed_update.add_field(name="Moeda", value=moeda_nome, inline=True)
        embed_update.add_field(
            name="📱 2v2 MOB",
            value=(
                f"T1 {len(mob1)}/2\n{render_team_mentions(mob1)}\n"
                f"T2 {len(mob2)}/2\n{render_team_mentions(mob2)}"
            ),
            inline=True
        )
        embed_update.add_field(
            name="💻 2v2 MISTO",
            value=(
                f"T1 {len(misto1)}/2\n{render_team_mentions(misto1)}\n"
                f"T2 {len(misto2)}/2\n{render_team_mentions(misto2)}"
            ),
            inline=True
        )
        if interaction.guild and interaction.guild.icon:
            embed_update.set_thumbnail(url=interaction.guild.icon.url)
        embed_update.set_footer(text=CREATOR_FOOTER)

        try:
            message = await interaction.channel.fetch_message(interaction.message.id)
            await message.edit(embed=embed_update)
        except Exception as e:
            log(f"❌ Erro ao atualizar painel 2v2 unificado: {e}")

    async def _join_team(self, interaction: discord.Interaction, mode: str, team_number: int):
        meta = await self._load_panel(interaction)
        if not meta:
            await interaction.followup.send("⚠️ Dados do painel não encontrados. Recrie o painel.", ephemeral=True)
            return

        bet_value = float(meta['bet_value'])
        mediator_fee = float(meta['mediator_fee'])
        currency_type = meta.get('currency_type', 'sonhos')
        message_id = interaction.message.id

        base_qid = self._base_qid(mode, message_id)
        team1_qid, team2_qid = self._team_qids(base_qid)

        user_id = interaction.user.id
        if db.is_user_in_active_bet(user_id):
            await interaction.followup.send("Você já está em uma aposta ativa.", ephemeral=True)
            return

        await self._ensure_lock(base_qid)

        async with queue_locks[base_qid]:
            team1 = db.get_queue(team1_qid)
            team2 = db.get_queue(team2_qid)

            if user_id in team1 or user_id in team2:
                await interaction.followup.send("Você já está nesta fila.", ephemeral=True)
                return

            target_team = team1 if team_number == 1 else team2
            if len(target_team) >= 2:
                await interaction.followup.send(f"Time {team_number} está cheio.", ephemeral=True)
                return

            db.add_to_queue(team1_qid if team_number == 1 else team2_qid, user_id)

        await self._update_panel(interaction, bet_value, currency_type)
        await interaction.followup.send(f"Você entrou no Time {team_number}.", ephemeral=True)
        await self._try_create_bet_if_full(interaction, mode, base_qid, bet_value, mediator_fee, currency_type)

    async def _try_create_bet_if_full(self, interaction: discord.Interaction, mode: str, base_qid: str, bet_value: float, mediator_fee: float, currency_type: str):
        team1_qid, team2_qid = self._team_qids(base_qid)
        team1 = db.get_queue(team1_qid)
        team2 = db.get_queue(team2_qid)
        if len(team1) < 2 or len(team2) < 2:
            return

        db.set_queue(team1_qid, [])
        db.set_queue(team2_qid, [])

        await self._update_panel(interaction, bet_value, currency_type)

        await create_bet_channel(
            interaction.guild,
            mode,
            team1[0],
            team2[0],
            float(bet_value),
            float(mediator_fee),
            interaction.channel_id,
            currency_type=currency_type,
        )

    @discord.ui.button(label='📱 2v2 MOB', style=discord.ButtonStyle.blurple, row=0, custom_id='persistent:panel_2v2_mob')
    async def choose_2v2_mob(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Escolha o time para entrar em 2v2 MOB:",
            ephemeral=True,
            view=self._team_selector_view("2v2-mob")
        )

    @discord.ui.button(label='💻 2v2 MISTO', style=discord.ButtonStyle.blurple, row=0, custom_id='persistent:panel_2v2_misto')
    async def choose_2v2_misto(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Escolha o time para entrar em 2v2 MISTO:",
            ephemeral=True,
            view=self._team_selector_view("2v2-misto")
        )

    def _team_selector_view(self, mode: str) -> discord.ui.View:
        parent = self

        class TeamSelector(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)

            @discord.ui.button(label="Time 1", style=discord.ButtonStyle.blurple, row=0)
            async def choose_team1(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.defer(ephemeral=True)
                await parent._join_team(interaction, mode, 1)
                self.stop()

            @discord.ui.button(label="Time 2", style=discord.ButtonStyle.blurple, row=0)
            async def choose_team2(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.defer(ephemeral=True)
                await parent._join_team(interaction, mode, 2)
                self.stop()

        return TeamSelector()

    @discord.ui.button(label='Sair da fila', style=discord.ButtonStyle.gray, row=1, custom_id='persistent:panel_2v2_leave')
    async def leave_panel_2v2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        meta = await self._load_panel(interaction)
        if not meta:
            await interaction.followup.send("⚠️ Dados do painel não encontrados. Recrie o painel.", ephemeral=True)
            return

        user_id = interaction.user.id
        message_id = interaction.message.id
        removed = False

        mob_base = self._base_qid("2v2-mob", message_id)
        misto_base = self._base_qid("2v2-misto", message_id)

        await self._ensure_lock(mob_base)
        await self._ensure_lock(misto_base)

        async with queue_locks[mob_base]:
            for qid in self._all_team_qids(message_id)[:2]:
                if user_id in db.get_queue(qid):
                    db.remove_from_queue(qid, user_id)
                    removed = True

        async with queue_locks[misto_base]:
            for qid in self._all_team_qids(message_id)[2:]:
                if user_id in db.get_queue(qid):
                    db.remove_from_queue(qid, user_id)
                    removed = True

        meta = db.get_panel_metadata(interaction.message.id) or {}
        currency_type = meta.get('currency_type', 'sonhos')
        await self._update_panel(interaction, float(meta['bet_value']), currency_type)
        await interaction.followup.send("Você saiu da fila." if removed else "Você não está em nenhuma fila deste painel.", ephemeral=True)


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
            # Usa menções diretas (economiza API calls)
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

            # Configura permissões para o mediador enviar mensagens e anexar arquivos
            try:
                await thread.set_permissions(
                    interaction.user,
                    overwrite=discord.PermissionOverwrite(
                        send_messages=True,
                        attach_files=True,
                        embed_links=True,
                        read_message_history=True
                    )
                )
                log(f"✅ Permissões configuradas para o mediador no tópico")
            except Exception as e:
                log(f"⚠️ Erro ao configurar permissões do mediador: {e}")

            await thread.send(f"<@{bet.player1_id}> <@{bet.player2_id}> Um mediador aceitou a aposta! ✅")


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
                    "Esta aposta não foi encontrada.\n"
                    "Use o comando /confirmar-pagamento dentro do tópico da aposta.",
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

    @discord.ui.button(label='Cancelar Aposta', style=discord.ButtonStyle.red, custom_id='persistent:cancel_bet')
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


# ==================== CENTRAL DE MEDIADORES ====================

class MediatorCentralPixModal(discord.ui.Modal, title='Informe sua Chave PIX'):
    """Modal para mediador informar seu PIX ao entrar no central"""
    pix_key = discord.ui.TextInput(
        label='Chave PIX',
        placeholder='Digite sua chave PIX (CPF, telefone, email, etc)',
        required=True,
        max_length=100
    )

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        pix = str(self.pix_key.value).strip()
        
        # Salva o PIX para próximas vezes
        db.save_mediator_pix(user_id, pix)
        
        # Adiciona ao central
        success = db.add_mediator_to_central(self.guild_id, user_id, pix)
        
        if not success:
            await interaction.response.send_message(
                "O Central de Mediadores está cheio (10 vagas). Tente novamente mais tarde.",
                ephemeral=True
            )
            return
        
        # Atualiza o painel do central
        await update_mediator_central_panel(interaction.guild)
        
        await interaction.response.send_message(
            f"Você entrou no Central de Mediadores!\n"
            f"Seu PIX foi salvo e será usado automaticamente nas próximas vezes.\n"
            f"Você será atribuído automaticamente quando uma aposta começar.\n"
            f"**Atenção:** Você será removido após 2 horas sem apostas.",
            ephemeral=True
        )
        log(f"✅ Mediador {user_id} entrou no central do guild {self.guild_id}")


class MediatorCentralView(discord.ui.View):
    """View do painel do Central de Mediadores"""
    def __init__(self, guild_id: int = None):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label='Aguardar Aposta', style=discord.ButtonStyle.green, custom_id='persistent:mediator_central_join', emoji='⏳')
    async def join_central_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        
        log(f"👆 Mediador {user_id} clicou em 'Aguardar Aposta' no central")
        
        # Verifica se tem cargo de mediador
        mediator_role_id = db.get_mediator_role(guild_id)
        has_mediator_role = mediator_role_id and discord.utils.get(interaction.user.roles, id=mediator_role_id) is not None
        
        if not has_mediator_role:
            if mediator_role_id:
                await interaction.response.send_message(
                    f"Você precisa ter o cargo <@&{mediator_role_id}> para entrar no central.",
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "Este servidor ainda não configurou um cargo de mediador.\n"
                    "Um administrador deve usar /setup @cargo para configurar.",
                    ephemeral=True
                )
            return
        
        # Verifica se já está no central
        if db.is_mediator_in_central(guild_id, user_id):
            await interaction.response.send_message(
                "Você já está no Central de Mediadores aguardando apostas.",
                ephemeral=True
            )
            return
        
        # Verifica se já tem PIX salvo
        saved_pix = db.get_mediator_pix(user_id)
        
        if saved_pix:
            # PIX já salvo - entra direto
            success = db.add_mediator_to_central(guild_id, user_id, saved_pix)
            
            if not success:
                await interaction.response.send_message(
                    "O Central de Mediadores está cheio (10 vagas). Tente novamente mais tarde.",
                    ephemeral=True
                )
                return
            
            # Atualiza o painel
            await update_mediator_central_panel(interaction.guild)
            
            await interaction.response.send_message(
                f"Você entrou no Central de Mediadores!\n"
                f"Usando seu PIX salvo: `{saved_pix}`\n"
                f"Você será atribuído automaticamente quando uma aposta começar.\n"
                f"**Atenção:** Você será removido após 2 horas sem apostas.",
                ephemeral=True
            )
            log(f"✅ Mediador {user_id} entrou no central (PIX já salvo)")
        else:
            # Precisa informar PIX - abre modal
            await interaction.response.send_modal(MediatorCentralPixModal(guild_id))

    @discord.ui.button(label='Sair do Central', style=discord.ButtonStyle.gray, custom_id='persistent:mediator_central_leave', emoji='🚪')
    async def leave_central_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        guild_id = interaction.guild.id
        
        if not db.is_mediator_in_central(guild_id, user_id):
            await interaction.response.send_message(
                "Você não está no Central de Mediadores.",
                ephemeral=True
            )
            return
        
        db.remove_mediator_from_central(guild_id, user_id)
        
        # Atualiza o painel
        await update_mediator_central_panel(interaction.guild)
        
        await interaction.response.send_message(
            "Você saiu do Central de Mediadores.",
            ephemeral=True
        )
        log(f"🚪 Mediador {user_id} saiu do central do guild {guild_id}")


async def update_mediator_central_panel(guild: discord.Guild):
    """Atualiza o painel do central de mediadores com a lista atual"""
    config = db.get_mediator_central_config(guild.id)
    if not config:
        return
    
    try:
        channel = guild.get_channel(config['channel_id'])
        if not channel:
            return
        
        message = await channel.fetch_message(config['message_id'])
        
        mediators = db.get_mediators_in_central(guild.id)
        vagas_ocupadas = len(mediators)
        vagas_disponiveis = 10 - vagas_ocupadas
        
        # Monta lista de mediadores com emojis
        if mediators:
            mediators_list = []
            for i, (user_id_str, data) in enumerate(mediators.items(), 1):
                mediators_list.append(f"👨‍⚖️ {i}. <@{user_id_str}>")
            mediators_text = "\n".join(mediators_list)
        else:
            mediators_text = "*🔍 Nenhum mediador aguardando*"
        
        embed = discord.Embed(
            title="🏢 Central de Mediadores",
            description="Mediadores podem aguardar aqui para serem atribuídos automaticamente às apostas.",
            color=EMBED_COLOR
        )
        embed.add_field(
            name=f"📋 Mediadores na Fila ({vagas_ocupadas}/10)",
            value=mediators_text,
            inline=False
        )
        embed.add_field(
            name="✅ Vagas Disponíveis",
            value=f"{vagas_disponiveis} vagas",
            inline=True
        )
        embed.add_field(
            name="⏰ Timeout",
            value="2 horas",
            inline=True
        )
        embed.add_field(
            name="📖 Como Funciona",
            value="1️⃣ Clique em **Aguardar Aposta**\n"
                  "2️⃣ Informe seu PIX (apenas na primeira vez)\n"
                  "3️⃣ Aguarde ser atribuído automaticamente\n"
                  "4️⃣ Após 2h sem apostas, você será removido",
            inline=False
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=CREATOR_FOOTER)
        
        await message.edit(embed=embed)
        log(f"📋 Painel do central atualizado: {vagas_ocupadas}/10 mediadores")
        
    except discord.NotFound:
        log(f"⚠️ Mensagem do central não encontrada - removendo configuração")
        db.delete_mediator_central_config(guild.id)
    except Exception as e:
        log(f"❌ Erro ao atualizar painel do central: {e}")


async def cleanup_expired_mediators_central():
    """Tarefa em background que remove mediadores que estão há mais de 2 horas no central"""
    await bot.wait_until_ready()
    log("⏰ Iniciando limpeza de mediadores expirados do central (a cada 10 minutos)")
    
    while not bot.is_closed():
        try:
            await asyncio.sleep(600)  # 10 minutos
            
            # Verifica todos os servidores com central configurado
            for guild in bot.guilds:
                if not db.is_mediator_central_configured(guild.id):
                    continue
                
                expired = db.get_expired_mediators_in_central(guild.id, timeout_hours=2)
                
                if expired:
                    for user_id in expired:
                        db.remove_mediator_from_central(guild.id, user_id)
                        log(f"⏰ Mediador {user_id} removido do central por timeout (2h)")
                        
                        # Tenta notificar o mediador via DM
                        try:
                            user = await bot.fetch_user(user_id)
                            await user.send(
                                f"Você foi removido do **Central de Mediadores** no servidor **{guild.name}** "
                                f"por ficar 2 horas sem receber apostas.\n\n"
                                f"Você pode entrar novamente a qualquer momento!"
                            )
                        except:
                            pass
                    
                    # Atualiza o painel
                    await update_mediator_central_panel(guild)
                    
        except Exception as e:
            log(f"❌ Erro na limpeza de mediadores do central: {e}")
            await asyncio.sleep(600)


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

                    # Extrai message_id do queue_id para buscar metadados
                    parts = queue_id.split('_')
                    if len(parts) < 2:
                        continue

                    try:
                        message_id = int(parts[-1])
                    except ValueError:
                        continue

                    # Busca informações da fila (de memória OU de metadados)
                    channel_id, mode, bet_value, currency_type = None, None, None, None

                    if queue_id in queue_messages:
                        # Usa dados em memória se disponíveis
                        channel_id, message_id, mode, bet_value, currency_type = queue_messages[queue_id]
                        log(f"📋 Usando dados em memória para {queue_id}")
                    else:
                        # Busca dos metadados se não estiver em memória (bot reiniciou)
                        metadata = db.get_queue_metadata(message_id)
                        if metadata:
                            channel_id = metadata['channel_id']
                            mode = metadata['mode']
                            bet_value = metadata['bet_value']
                            currency_type = metadata.get('currency_type', 'sonhos')
                            # Reidrata queue_messages para próximas operações
                            queue_messages[queue_id] = (channel_id, message_id, mode, bet_value, currency_type)
                            log(f"🔄 Reidratado dados para {queue_id} a partir dos metadados")
                        else:
                            log(f"⚠️ Metadados não encontrados para {queue_id}, pulando atualização")
                            continue

                    # PRIMEIRO atualiza o painel (mostra "Vazio" se necessário)
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

                                # Formata valor baseado na moeda
                                if currency_type == "sonhos":
                                    valor_formatado = format_sonhos(bet_value)
                                else:
                                    valor_formatado = f"$ {bet_value:.2f}"

                                embed.add_field(name="Valor", value=valor_formatado, inline=True)
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

                                # Formata valor baseado na moeda
                                if currency_type == "sonhos":
                                    valor_formatado = format_sonhos(bet_value)
                                else:
                                    valor_formatado = f"$ {bet_value:.2f}"

                                embed.add_field(name="Valor", value=valor_formatado, inline=True)
                                embed.add_field(name="Fila", value=players_text, inline=True)
                                if channel.guild and channel.guild.icon:
                                    embed.set_thumbnail(url=channel.guild.icon.url)

                            await message.edit(embed=embed)
                            log(f"✅ Painel {queue_id} atualizado com sucesso")
                    except discord.NotFound:
                        log(f"⚠️ Mensagem do painel {queue_id} não encontrada - ignorando atualização")
                    except Exception as e:
                        log(f"⚠️ Erro ao atualizar mensagem da fila {queue_id}: {e}")

                    # NÃO limpa metadados - fila deve ficar sempre disponível 24/7
                    # Removido: limpeza de metadados quando fila fica vazia
                    # A fila permanece disponível para novos jogadores entrarem a qualquer momento

            # Aguarda 60 segundos antes de verificar novamente (economiza processamento)
            await asyncio.sleep(60)

        except Exception as e:
            log(f"Erro na limpeza de filas: {e}")
            await asyncio.sleep(60)


@bot.event
async def on_message_delete(message):
    """Detecta quando uma mensagem de painel é deletada

    IMPORTANTE: NÃO deletamos metadados para permitir que os botões
    funcionem indefinidamente, mesmo após reinicializações do bot.
    Os jogadores na fila são limpos, mas os metadados são mantidos.
    """
    try:
        # Verifica se a mensagem deletada tinha metadados de fila
        metadata = db.get_queue_metadata(message.id)

        if metadata:
            if metadata.get('type') == 'panel':
                panel_type = metadata.get('panel_type')
                log(f"🗑️ Mensagem de painel deletada (ID: {message.id})")

                data = db._load_data()
                if panel_type == '1v1':
                    mob_qid = f"1v1-mob_{message.id}"
                    misto_qid = f"1v1-misto_{message.id}"
                    for qid in (mob_qid, misto_qid):
                        if qid in data.get('queues', {}):
                            data['queues'][qid] = []
                        if qid in data.get('queue_timestamps', {}):
                            data['queue_timestamps'][qid] = {}
                elif panel_type == '2v2':
                    mob_base = f"2v2-mob_{message.id}"
                    misto_base = f"2v2-misto_{message.id}"
                    qids = [
                        f"{mob_base}_team1", f"{mob_base}_team2",
                        f"{misto_base}_team1", f"{misto_base}_team2",
                    ]
                    for qid in qids:
                        if qid in data.get('queues', {}):
                            data['queues'][qid] = []
                        if qid in data.get('queue_timestamps', {}):
                            data['queue_timestamps'][qid] = {}

                db._save_data(data)
                log(f"✅ Painel {panel_type} limpo (metadados preservados para reuso)")
                return

            queue_id = metadata['queue_id']
            log(f"🗑️ Mensagem de painel deletada (ID: {message.id})")
            log(f"🧹 Limpando apenas jogadores da fila {queue_id} (metadados preservados)...")

            # NÃO REMOVE METADADOS - mantém para sempre para que botões funcionem indefinidamente
            # Comentado: db.delete_queue_metadata(message.id)

            # Remove do dicionário em memória
            if queue_id in queue_messages:
                del queue_messages[queue_id]

            # Limpa apenas a fila de jogadores (remove todos jogadores)
            # mas mantém os metadados para que possam criar nova fila no mesmo painel
            data = db._load_data()
            if queue_id in data.get('queues', {}):
                data['queues'][queue_id] = []  # Limpa jogadores ao invés de deletar
                log(f"✅ Jogadores da fila {queue_id} removidos")
            if queue_id in data.get('queue_timestamps', {}):
                data['queue_timestamps'][queue_id] = {}  # Limpa timestamps ao invés de deletar
            db._save_data(data)

            log(f"✅ Fila {queue_id} limpa (metadados preservados para reuso)")
    except Exception as e:
        log(f"⚠️ Erro ao processar mensagem deletada: {e}")

@bot.event
async def on_guild_join(guild: discord.Guild):
    """Quando o bot entra em um servidor, verifica se está autorizado"""
    log(f"➕ Bot adicionado ao servidor: {guild.name} ({guild.id})")

    # Apenas chama ensure_guild_authorized - ele já faz tudo (enviar aviso, criar convite, notificar criador e sair)
    await ensure_guild_authorized(guild)

@bot.event
async def on_ready():
    log("=" * 50)
    log("✅ BOT CONECTADO AO DISCORD!")
    log("=" * 50)
    log(f'👤 Usuário: {bot.user}')
    log(f'📛 Nome: {bot.user.name}')
    log(f'🆔 ID: {bot.user.id}')
    log(f'🌐 Servidores: {len(bot.guilds)}')

    # Configura status "Não Perturbe" com atividade customizada
    try:
        activity = discord.CustomActivity(name="Saiba mais na bio")
        await bot.change_presence(
            status=discord.Status.dnd,  # DND = "Não Perturbe"
            activity=activity
        )
        log("✅ Status configurado: Não Perturbe - 'Saiba mais na bio'")
    except Exception as e:
        log(f"⚠️ Erro ao configurar status: {e}")

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
        bot.add_view(TeamQueueButton(mode="2v2-misto", bet_value=0, mediator_fee=0, currency_type="sonhos"))
        bot.add_view(Unified1v1PanelView())
        bot.add_view(Unified2v2PanelView())
        bot.add_view(ConfirmPaymentButton(bet_id=""))
        bot.add_view(AcceptMediationButton(bet_id=""))
        bot.add_view(MediatorCentralView())
        bot._persistent_views_registered = True
        log('✅ Views persistentes registradas (QueueButton, ConfirmPaymentButton, AcceptMediationButton, MediatorCentralView)')
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
            if metadata.get('type') == 'panel':
                continue
            queue_id = metadata['queue_id']
            channel_id = metadata['channel_id']
            message_id = metadata['message_id']
            mode = metadata['mode']
            bet_value = metadata['bet_value']
            currency_type = metadata.get('currency_type', 'sonhos')

            # Restaura no dicionário em memória (com currency_type)
            queue_messages[queue_id] = (channel_id, message_id, mode, bet_value, currency_type)

            # Log detalhado de cada fila recuperada
            current_queue = db.get_queue(queue_id)
            log(f'📋 Fila {queue_id}: {len(current_queue)} jogadores')

        log(f'✅ {len(all_metadata)} filas recuperadas e sincronizadas')
        bot._queue_metadata_recovered = True

    # Inicia a tarefa de limpeza automática de filas (apenas uma vez)
    if not hasattr(bot, '_cleanup_task_started'):
        bot.loop.create_task(cleanup_expired_queues())
        bot.loop.create_task(cleanup_orphaned_data_task())
        bot.loop.create_task(cleanup_expired_mediators_central())
        bot._cleanup_task_started = True
        log('🧹 Tarefas de limpeza iniciadas')
    else:
        log('ℹ️ Tarefas de limpeza já estavam rodando')

    # Inicia a tarefa de verificação de assinaturas (apenas uma vez)
    if not hasattr(bot, '_subscription_task_started'):
        check_expired_subscriptions.start()
        bot._subscription_task_started = True
        log('🔐 Tarefa de verificação de assinaturas iniciada')

    # Garante assinatura permanente do servidor auto-autorizado
    if not hasattr(bot, '_auto_authorized_setup'):
        auto_guild = bot.get_guild(AUTO_AUTHORIZED_GUILD_ID)
        if auto_guild:
            if not db.is_subscription_active(AUTO_AUTHORIZED_GUILD_ID):
                db.create_subscription(AUTO_AUTHORIZED_GUILD_ID, None)
                log(f"✅ Assinatura permanente automática criada para {auto_guild.name}")
        bot._auto_authorized_setup = True

    # Auto-autoriza servidores existentes no restart (apenas na primeira vez)
    if not hasattr(bot, '_initial_guild_check'):
        log('🔍 Auto-autorizando servidores onde o bot já está...')
        auto_authorized_count = 0
        for guild in bot.guilds:
            # Pula o servidor auto-autorizado (já tem lógica específica acima)
            if guild.id == AUTO_AUTHORIZED_GUILD_ID:
                continue

            # Se o servidor não tem assinatura ativa, cria por 5 dias automaticamente
            if not db.is_subscription_active(guild.id):
                duration_seconds = 5 * 86400  # 5 dias
                db.create_subscription(guild.id, duration_seconds)
                log(f"✅ Auto-autorizado: {guild.name} ({guild.id}) - assinatura de 5 dias criada")
                auto_authorized_count += 1

                # Notifica o criador via DM
                try:
                    creator = await bot.fetch_user(CREATOR_ID)
                    from datetime import datetime, timedelta
                    expires_at = datetime.now() + timedelta(seconds=duration_seconds)

                    embed = discord.Embed(
                        title="🔔 Servidor Auto-Autorizado (Restart)",
                        description=f"O bot auto-autorizou um servidor ao reiniciar",
                        color=0x00FF00
                    )
                    embed.add_field(name="Servidor", value=f"{guild.name}", inline=False)
                    embed.add_field(name="ID", value=f"`{guild.id}`", inline=True)
                    embed.add_field(name="Duração", value="5 dias", inline=True)
                    embed.add_field(name="Expira em", value=expires_at.strftime('%d/%m/%Y %H:%M'), inline=False)
                    embed.set_footer(text=CREATOR_FOOTER)

                    await creator.send(embed=embed)
                    log(f"📨 DM enviada ao criador sobre auto-autorização de {guild.name}")
                except Exception as e:
                    log(f"⚠️ Erro ao enviar DM ao criador: {e}")

        if auto_authorized_count > 0:
            log(f'🎉 {auto_authorized_count} servidor(es) auto-autorizado(s) por 5 dias')

        bot._initial_guild_check = True
        log('✅ Verificação inicial de servidores concluída')


@bot.event
async def on_disconnect():
    """Evento disparado quando o bot perde conexão com o Discord"""
    log("⚠️ BOT DESCONECTADO DO DISCORD")
    log("🔄 Tentando reconectar automaticamente...")

@bot.event
async def on_resumed():
    """Evento disparado quando o bot retoma a conexão após desconexão"""
    log("=" * 50)
    log("✅ BOT RECONECTADO AO DISCORD!")
    log("=" * 50)
    log(f'👤 Sessão retomada: {bot.user}')
    log(f'🌐 Servidores: {len(bot.guilds)}')

    # PROTEÇÃO EXTRA: Verifica se queue_messages está sincronizado com o banco
    try:
        all_metadata = db.get_all_queue_metadata()

        # Se queue_messages estiver vazio mas há metadados no banco, recupera
        if not queue_messages and all_metadata:
            log('⚠️ Detectado queue_messages vazio após reconexão - recuperando do banco...')
            for message_id_str, metadata in all_metadata.items():
                if metadata.get('type') == 'panel':
                    continue
                queue_id = metadata['queue_id']
                channel_id = metadata['channel_id']
                message_id = metadata['message_id']
                mode = metadata['mode']
                bet_value = metadata['bet_value']
                currency_type = metadata.get('currency_type', 'sonhos')
                queue_messages[queue_id] = (channel_id, message_id, mode, bet_value, currency_type)
            log(f'✅ {len(all_metadata)} filas recuperadas após reconexão')
        else:
            log(f'✅ queue_messages sincronizado: {len(queue_messages)} filas em memória')
    except Exception as e:
        log(f'⚠️ Erro ao verificar sincronização de filas após reconexão: {e}')

@bot.event
async def on_connect():
    """Evento disparado quando o bot estabelece conexão (primeira vez ou reconexão)"""
    log("🔌 Conexão estabelecida com o Discord Gateway")


def register_all_commands(target_bot):
    """
    Copia todos os comandos do bot principal para outro bot.
    Usa método nativo do discord.py para garantir compatibilidade total.
    """
    log(f"📋 Copiando comandos do bot principal para o bot alvo...")
    
    # Copia todos os comandos (grupos e comandos individuais)
    for command in bot.tree.walk_commands():
        try:
            # Se for um comando de grupo, copia o grupo inteiro
            if isinstance(command, app_commands.Group):
                target_bot.tree.add_command(command.copy())
                log(f"  ✅ Grupo /{command.name} copiado")
            # Se for um comando normal, copia individualmente
            elif isinstance(command, app_commands.Command):
                # Cria uma cópia profunda do comando com callback preservado
                new_command = app_commands.Command(
                    name=command.name,
                    description=command.description,
                    callback=command.callback,
                    parent=command.parent
                )
                # Copia parâmetros
                if hasattr(command, '_params'):
                    new_command._params = command._params.copy()
                
                # Copia extras se existir
                if hasattr(command, 'extras') and command.extras:
                    new_command.extras = command.extras.copy()
                
                # Copia guild_ids apenas se existir
                if hasattr(command, 'guild_ids') and command.guild_ids:
                    new_command.guild_ids = command.guild_ids.copy()
                
                target_bot.tree.add_command(new_command)
                log(f"  ✅ Comando /{command.name} copiado")
        except Exception as e:
            log(f"  ⚠️ Erro ao copiar comando /{command.name}: {e}")
    
    log(f"✅ Comandos copiados para o bot alvo")


@bot.tree.command(name="mostrar-fila", description="[MODERADOR] Criar mensagem com botão para entrar na fila")
@app_commands.describe(
    modo="Escolha o modo de jogo",
    valor="Valor da aposta (exemplo: 50k, 1.5m, 2000)",
    taxa="Taxa do mediador (exemplo: 5%, 500, 1k)",
    moeda="Tipo de moeda da aposta (Dinheiro ou Sonhos)"
)
@app_commands.choices(modo=[
    app_commands.Choice(name="Painel 1v1", value="1v1"),
    app_commands.Choice(name="Painel 2v2", value="2v2"),
])
@app_commands.choices(moeda=[
    app_commands.Choice(name="Dinheiro", value="reais"),
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

    panel_type = modo.value
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
        valor_formatado = f"$ {valor_numerico:.2f}"

    embed = discord.Embed(
        title="Painel 2v2" if panel_type == "2v2" else "Painel 1v1",
        color=EMBED_COLOR
    )

    embed.add_field(name="Valor", value=valor_formatado, inline=True)
    embed.add_field(name="Moeda", value=moeda.name, inline=True)
    if panel_type == "2v2":
        embed.add_field(
            name="📱 2v2 MOB",
            value=(
                f"T1 0/2\nT2 0/2"
            ),
            inline=True
        )
        embed.add_field(
            name="💻 2v2 MISTO",
            value=(
                f"T1 0/2\nT2 0/2"
            ),
            inline=True
        )
    else:
        embed.add_field(name="📱 1v1 MOB", value="0/2\nVazio", inline=True)
        embed.add_field(name="💻 1v1 MISTO", value="0/2\nVazio", inline=True)
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=CREATOR_FOOTER)

    # Defer a resposta para evitar timeout
    await interaction.response.defer()

    # Envia a mensagem primeiro
    message = await interaction.followup.send(embed=embed, wait=True)

    log(f"Mensagem da fila criada com ID: {message.id}")

    view = Unified2v2PanelView() if panel_type == "2v2" else Unified1v1PanelView()

    db.save_panel_metadata(message.id, panel_type, valor_numerico, taxa_numerica, interaction.channel.id, currency_type)
    log(f"Metadados do painel salvos: panel_type={panel_type}, bet_value={valor_numerico}, mediator_fee={taxa_numerica}, currency={currency_type}")

    # Agora edita a mensagem com os botões
    await message.edit(embed=embed, view=view)
    log(f"Painel criado e pronto para uso: {panel_type} com moeda {currency_type}")


@bot.tree.command(name="preset-filas", description="[MODERADOR] Criar várias filas com valores pré-definidos")

@app_commands.describe(
    modo="Escolha o modo de jogo",
    taxa="Taxa do mediador (exemplo: 5%, 500, 1k)",
    moeda="Tipo de moeda da aposta (Dinheiro ou Sonhos)"
)
@app_commands.choices(modo=[
    app_commands.Choice(name="Painel 1v1", value="1v1"),
    app_commands.Choice(name="Painel 2v2", value="2v2"),
])
@app_commands.choices(moeda=[
    app_commands.Choice(name="Dinheiro", value="reais"),
    app_commands.Choice(name="Sonhos", value="sonhos"),
])
async def preset_filas(interaction: discord.Interaction, modo: app_commands.Choice[str], taxa: str, moeda: app_commands.Choice[str]):
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

    panel_type = modo.value
    currency_type = moeda.value

    # Define valores preset baseado na moeda
    if currency_type == "reais":
        preset_values = [50, 40, 35, 30, 25, 20, 15, 10, 7, 5, 3, 2, 1]
    else:  # sonhos
        preset_values = [2000000, 1000000, 800000, 500000, 300000, 200000, 100000, 50000]

    # Processa a taxa (pode ser porcentagem ou valor fixo)
    taxa_str = str(taxa).strip()

    # Defer a resposta para evitar timeout
    await interaction.response.defer(ephemeral=True)

    log(f"🎯 Criando preset de filas: modo={modo.value}, moeda={currency_type}, taxa={taxa_str}")

    created_count = 0
    tasks = []

    for valor_numerico in preset_values:
        try:
            # Calcula a taxa para cada valor
            if taxa_str.endswith('%'):
                # Remove o % e calcula a porcentagem do valor
                try:
                    percentual = float(taxa_str[:-1])
                    taxa_numerica = (percentual / 100) * valor_numerico
                except ValueError:
                    await interaction.followup.send(
                        "Taxa inválida. Use valores como: 5%, 500, 1k",
                        ephemeral=True
                    )
                    return
            else:
                # Converte usando parse_value
                taxa_numerica = parse_value(taxa_str)

            if taxa_numerica < 0:
                await interaction.followup.send(
                    "Taxa inválida. Use valores não-negativos (exemplos: 5%, 500, 1k).",
                    ephemeral=True
                )
                return

            # Formata o valor baseado no tipo de moeda
            if currency_type == "sonhos":
                valor_formatado = format_sonhos(valor_numerico)
            else:
                valor_formatado = f"$ {valor_numerico:.2f}"

            embed = discord.Embed(
                title="Painel 2v2" if panel_type == "2v2" else "Painel 1v1",
                color=EMBED_COLOR
            )

            embed.add_field(name="Valor", value=valor_formatado, inline=True)
            embed.add_field(name="Moeda", value=moeda.name, inline=True)
            if panel_type == "2v2":
                embed.add_field(
                    name="📱 2v2 MOB",
                    value=(
                        f"T1 0/2\nT2 0/2"
                    ),
                    inline=True
                )
                embed.add_field(
                    name="💻 2v2 MISTO",
                    value=(
                        f"T1 0/2\nT2 0/2"
                    ),
                    inline=True
                )
            else:
                embed.add_field(name="📱 1v1 MOB", value="0/2\nVazio", inline=True)
                embed.add_field(name="💻 1v1 MISTO", value="0/2\nVazio", inline=True)
            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)
            embed.set_footer(text=CREATOR_FOOTER)

            # Envia a mensagem primeiro SEM botão (mais rápido)
            message = await interaction.channel.send(embed=embed)

            log(f"📋 Fila preset criada: {valor_formatado} (ID: {message.id})")

            view = Unified2v2PanelView() if panel_type == "2v2" else Unified1v1PanelView()

            db.save_panel_metadata(message.id, panel_type, valor_numerico, taxa_numerica, interaction.channel.id, currency_type)

            # Adiciona a tarefa de editar com botões à lista (será executado em batch)
            tasks.append((message, embed, view, valor_formatado))
            created_count += 1

        except Exception as e:
            log(f"❌ Erro ao criar fila preset para valor {valor_numerico}: {e}")
            continue

    # AGORA adiciona os botões em todas as filas de uma vez (muito mais rápido!)
    log(f"⚡ Adicionando botões em {len(tasks)} filas...")
    for message, embed, view, valor_formatado in tasks:
        try:
            await message.edit(embed=embed, view=view)
            log(f"✅ Botão adicionado em {valor_formatado}")
        except Exception as e:
            log(f"❌ Erro ao adicionar botão em {valor_formatado}: {e}")

    # Confirma criação
    await interaction.followup.send(
        f"✅ {created_count} filas criadas com sucesso!\n"
        f"Modo: {modo.name}\n"
        f"Moeda: {moeda.name}\n"
        f"Taxa: {taxa_str}",
        ephemeral=True
    )

    log(f"✅ Preset de filas concluído: {created_count} filas criadas")


async def create_bet_channel(guild: discord.Guild, mode: str, player1_id: int, player2_id: int, bet_value: float, mediator_fee: float, source_channel_id: int = None, team1_ids: Optional[list[int]] = None, team2_ids: Optional[list[int]] = None, currency_type: str = None):
    log(f"🔧 create_bet_channel chamada: mode={mode}, player1={player1_id}, player2={player2_id}, bet_value={bet_value}, mediator_fee={mediator_fee}")

    # VALIDAÇÃO CRÍTICA: Nunca permitir valores zero
    if bet_value <= 0 or mediator_fee < 0:
        log(f"❌ ERRO CRÍTICO: Valores inválidos - bet_value={bet_value}, mediator_fee={mediator_fee}. Abortando criação.")
        return

    team1_ids = team1_ids or []
    team2_ids = team2_ids or []
    all_player_ids = list({player1_id, player2_id, *team1_ids, *team2_ids})

    # Validação dupla com lock para evitar race condition
    for uid in all_player_ids:
        if db.is_user_in_active_bet(uid):
            log(f"❌ Um dos jogadores já está em uma aposta ativa. Abortando criação.")
            return

    for uid in all_player_ids:
        db.remove_from_all_queues(uid)
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

        extra_members: list[discord.Member] = []
        if is_2v2_mode(mode):
            extra_ids = [uid for uid in (team1_ids + team2_ids) if uid not in (player1_id, player2_id)]
            for uid in extra_ids:
                m = guild.get_member(uid)
                if not m:
                    m = await guild.fetch_member(uid)
                extra_members.append(m)

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
        if is_2v2_mode(mode):
            thread_name = "Aposta: Time 1 vs Time 2"
        else:
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
            for m in extra_members:
                await thread.add_user(m)
            log(f"✅ Jogadores adicionados ao tópico")
        except Exception as e:
            log(f"⚠️ Erro ao adicionar jogadores ao tópico: {e}")

        # Configura permissões para os jogadores enviarem mensagens e anexarem arquivos
        try:
            # Permissões: enviar mensagens, anexar arquivos, enviar embeds, ler histórico
            overwrites = {
                player1: discord.PermissionOverwrite(
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True
                ),
                player2: discord.PermissionOverwrite(
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True
                )
            }
            for m in extra_members:
                overwrites[m] = discord.PermissionOverwrite(
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True
                )

            # Aplica permissões ao thread
            for member, overwrite in overwrites.items():
                await thread.set_permissions(member, overwrite=overwrite)
            log(f"✅ Permissões configuradas para os jogadores no tópico")
        except Exception as e:
            log(f" Erro ao configurar permissões do tópico: {e}")

        bet_id = f"{player1_id}_{player2_id}_{int(datetime.now().timestamp())}"

        # Log final antes de criar o objeto Bet
        log(f" Criando objeto Bet com valores: bet_value={bet_value}, mediator_fee={mediator_fee}")
        log(f" Thread criado com ID: {thread.id} (type={type(thread.id)})")

        # Determina currency_type (prioridade: argumento -> metadados antigos)
        if currency_type is None:
            currency_type = 'sonhos'  # Valor padrão

            # Tenta encontrar nos metadados salvos (painéis antigos / filas antigas)
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
            team1_ids=team1_ids,
            team2_ids=team2_ids,
            mediator_id=0,
            channel_id=thread.id,
            bet_value=float(bet_value),
            mediator_fee=float(mediator_fee),
            currency_type=currency_type
        )

        db.add_active_bet(bet)

        log(f" Bet criado e salvo no banco:")
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
    log(f" Criando embed com valores: bet_value={bet_value}, mediator_fee={mediator_fee}")

    # Formata valores usando a função format_sonhos
    valor_formatado = format_sonhos(float(bet_value))
    taxa_formatada = format_sonhos(float(mediator_fee))

    log(f" Valores formatados: {valor_formatado} / {taxa_formatada}")

    # ========== CENTRAL DE MEDIADORES - ATRIBUIÇÃO AUTOMÁTICA ==========
    # Verifica se o Central de Mediadores está configurado
    central_configured = db.is_mediator_central_configured(guild.id)
    auto_mediator = None
    auto_mediator_pix = None

    if central_configured:
        log(f" Central de Mediadores está configurado para guild {guild.id}")

        # Tenta pegar o primeiro mediador da fila (sistema FIFO)
        mediator_data = db.get_first_mediator_from_central(guild.id)

        if mediator_data:
            auto_mediator_id, auto_mediator_pix = mediator_data
            log(f" Mediador automático selecionado: {auto_mediator_id}")

            # Remove o mediador do central (já foi atribuído)
            db.remove_mediator_from_central(guild.id, auto_mediator_id)

            # Atualiza a aposta com o mediador automático
            bet.mediator_id = auto_mediator_id
            bet.mediator_pix = auto_mediator_pix
            db.update_active_bet(bet)

            # Busca o membro do mediador
            auto_mediator = guild.get_member(auto_mediator_id)
            if not auto_mediator:
                try:
                    auto_mediator = await guild.fetch_member(auto_mediator_id)
                except:
                    log(f" Não foi possível encontrar o mediador {auto_mediator_id}")
                    auto_mediator = None
                    # Limpa o mediador da aposta se não encontrou
                    bet.mediator_id = 0
                    bet.mediator_pix = ""
                    db.update_active_bet(bet)

            # Atualiza o painel do central
            await update_mediator_central_panel(guild)
        else:
            log(f" Central configurado mas sem mediadores disponíveis")

    # Se tem mediador automático atribuído
    if auto_mediator:
        # Adiciona o mediador ao tópico
        try:
            await thread.add_user(auto_mediator)
            await thread.set_permissions(
                auto_mediator,
                overwrite=discord.PermissionOverwrite(
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True
                )
            )
            log(f" Mediador {auto_mediator.name} adicionado ao tópico")
        except Exception as e:
            log(f" Erro ao adicionar mediador ao tópico: {e}")

        # Cria embed de mediador já aceito
        embed = discord.Embed(
            title="Aposta Criada - Mediador Atribuído Automaticamente",
            color=EMBED_COLOR
        )
        embed.add_field(name="Modo", value=mode.replace("-", " ").title(), inline=True)
        embed.add_field(name="Valor da Aposta", value=valor_formatado, inline=True)
        embed.add_field(name="Taxa do Mediador", value=taxa_formatada, inline=True)
        if is_2v2_mode(mode):
            embed.add_field(name="Time 1", value="\n".join([f"<@{uid}>" for uid in team1_ids]), inline=True)
            embed.add_field(name="Time 2", value="\n".join([f"<@{uid}>" for uid in team2_ids]), inline=True)
        else:
            embed.add_field(name="Jogadores", value=f"{player1.mention} vs {player2.mention}", inline=False)
        embed.add_field(name="Mediador", value=auto_mediator.mention, inline=True)

        # Mostra PIX apenas se for aposta em reais
        if currency_type != "sonhos":
            embed.add_field(name="PIX", value=f"`{auto_mediator_pix}`", inline=True)
            embed.add_field(
                name="Instrução",
                value="Envie o pagamento e clique no botão abaixo para confirmar",
                inline=False
            )
        else:
            embed.add_field(
                name="Instrução",
                value=f"Transfiram **{valor_formatado}** Sonhos para {auto_mediator.mention} usando a Loritta",
                inline=False
            )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=CREATOR_FOOTER)

        confirm_view = ConfirmPaymentButton(bet_id)
        await thread.send(
            content=f"{player1.mention} {player2.mention} Aposta criada! Mediador atribuído automaticamente: {auto_mediator.mention}",
            embed=embed,
            view=confirm_view
        )

        # Notifica o mediador via DM
        try:
            await auto_mediator.send(
                f"Você foi atribuído automaticamente como mediador de uma aposta no servidor **{guild.name}**!\n\n"
                f"**Jogadores:** {player1.name} vs {player2.name}\n"
                f"**Valor:** {valor_formatado}\n"
                f"**Taxa:** {taxa_formatada}\n\n"
                f"Acesse o tópico da aposta para mediar."
            )
        except:
            pass
    else:
        # Comportamento normal - aguardar mediador
        embed = discord.Embed(
            title="Aposta - Aguardando Mediador",
            description=admin_mention,
            color=EMBED_COLOR
        )
        embed.add_field(name="Modo", value=mode.replace("-", " ").title(), inline=True)
        embed.add_field(name="Valor da Aposta", value=valor_formatado, inline=True)
        embed.add_field(name="Taxa do Mediador", value=taxa_formatada, inline=True)
        if is_2v2_mode(mode):
            embed.add_field(name="Time 1", value="\n".join([f"<@{uid}>" for uid in team1_ids]), inline=True)
            embed.add_field(name="Time 2", value="\n".join([f"<@{uid}>" for uid in team2_ids]), inline=True)
        else:
            embed.add_field(name="Jogadores", value=f"{player1.mention} vs {player2.mention}", inline=False)

        # Se o central está configurado mas não tem mediador, avisa
        if central_configured:
            embed.add_field(
                name="Aviso",
                value="Não há mediadores disponíveis no Central de Mediadores no momento.\n"
                      "Aguarde um mediador aceitar manualmente.",
                inline=False
            )

        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=CREATOR_FOOTER)

        view = AcceptMediationButton(bet_id)

        await thread.send(
            content=f"{player1.mention} {player2.mention} Aposta criada! Aguardando mediador... {admin_mention}",
            embed=embed,
            view=view
        )


@bot.tree.command(name="motrar-fila", description="[MODERADOR] Alias para /mostrar-fila")
@app_commands.describe(
    modo="Escolha o modo de jogo",
    valor="Valor da aposta (exemplo: 50k, 1.5m, 2000)",
    taxa="Taxa do mediador (exemplo: 5%, 500, 1k)",
    moeda="Tipo de moeda da aposta (Dinheiro ou Sonhos)"
)
@app_commands.choices(modo=[
    app_commands.Choice(name="Painel 1v1", value="1v1"),
    app_commands.Choice(name="Painel 2v2", value="2v2"),
])
@app_commands.choices(moeda=[
    app_commands.Choice(name="Dinheiro", value="reais"),
    app_commands.Choice(name="Sonhos", value="sonhos"),
])
async def motrar_fila(interaction: discord.Interaction, modo: app_commands.Choice[str], valor: str, taxa: str, moeda: app_commands.Choice[str]):
    await mostrar_fila(interaction, modo, valor, taxa, moeda)


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

    # ========== DEVOLVE MEDIADOR AO FINAL DA FILA ==========
    # Se tinha mediador automático do central, devolve ao final da fila
    if bet.mediator_id and bet.mediator_pix:
        central_configured = db.is_mediator_central_configured(interaction.guild.id)
        if central_configured:
            success = db.add_mediator_to_end_of_central(interaction.guild.id, bet.mediator_id, bet.mediator_pix)
            if success:
                log(f"🔄 Mediador {bet.mediator_id} devolvido ao final da fila do central")
                await update_mediator_central_panel(interaction.guild)
            else:
                log(f"⚠️ Não foi possível devolver mediador {bet.mediator_id} à fila (cheia ou central não configurado)")

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

    # NÃO deletar painéis de fila - eles podem ser reutilizados indefinidamente!
    # Apenas limpar os jogadores das filas (preservando metadados)

    # Limpar apenas as listas de jogadores nas filas (mantém metadados para reuso)
    data = db._load_data()

    # Limpar jogadores de todas as filas
    if 'queues' in data:
        for queue_id in data['queues'].keys():
            data['queues'][queue_id] = []  # Limpa jogadores mas mantém a estrutura

    # Limpar timestamps
    if 'queue_timestamps' in data:
        for queue_id in data['queue_timestamps'].keys():
            data['queue_timestamps'][queue_id] = {}  # Limpa timestamps mas mantém a estrutura

    # CRÍTICO: NÃO DELETAR queue_metadata - painéis devem funcionar para sempre!
    # Os metadados são preservados para que os painéis continuem funcionando

    db._save_data(data)

    log(f"✅ Filas limpas (metadados preservados para reuso dos painéis)")

    # Limpar dicionário em memória
    queue_messages.clear()

    embed = discord.Embed(
        title="Sistema Desbugado",
        description="Todas as apostas ativas foram canceladas e filas limpas.\n\n✅ **Painéis preservados** - Os painéis de fila continuam funcionando e podem ser reutilizados!",
        color=EMBED_COLOR
    )
    embed.add_field(name="Apostas Canceladas", value=str(cancelled_bets), inline=True)
    embed.add_field(name="Canais Deletados", value=str(deleted_channels), inline=True)
    embed.add_field(name="Filas Limpas", value="Todas (jogadores removidos)", inline=True)
    embed.add_field(name="Painéis", value="Preservados para reuso ♻️", inline=True)
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


@bot.tree.command(name="central-apostado", description="[ADMIN] Criar painel do Central de Mediadores")
async def central_apostado(interaction: discord.Interaction):
    """Cria o painel do Central de Mediadores onde mediadores podem aguardar apostas"""
    
    # Apenas administradores podem usar este comando
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "Apenas administradores podem usar este comando.",
            ephemeral=True
        )
        return
    
    # Verifica se já existe um central configurado
    existing_config = db.get_mediator_central_config(interaction.guild.id)
    if existing_config:
        # Remove configuração antiga
        db.delete_mediator_central_config(interaction.guild.id)
        log(f"♻️ Central anterior removido, criando novo")
    
    # Cria o embed do painel com emojis
    embed = discord.Embed(
        title="🏢 Central de Mediadores",
        description="Mediadores podem aguardar aqui para serem atribuídos automaticamente às apostas.",
        color=EMBED_COLOR
    )
    embed.add_field(
        name="📋 Mediadores na Fila (0/10)",
        value="*🔍 Nenhum mediador aguardando*",
        inline=False
    )
    embed.add_field(
        name="✅ Vagas Disponíveis",
        value="10 vagas",
        inline=True
    )
    embed.add_field(
        name="⏰ Timeout",
        value="2 horas",
        inline=True
    )
    embed.add_field(
        name="📖 Como Funciona",
        value="1️⃣ Clique em **Aguardar Aposta**\n"
              "2️⃣ Informe seu PIX (apenas na primeira vez)\n"
              "3️⃣ Aguarde ser atribuído automaticamente\n"
              "4️⃣ Após 2h sem apostas, você será removido",
        inline=False
    )
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)
    embed.set_footer(text=CREATOR_FOOTER)
    
    # Envia o painel com os botões
    view = MediatorCentralView(interaction.guild.id)
    await interaction.response.send_message(embed=embed, view=view)
    
    # Busca a mensagem enviada para salvar o ID
    message = await interaction.original_response()
    
    # Salva a configuração
    db.save_mediator_central_config(interaction.guild.id, interaction.channel.id, message.id)
    
    log(f"✅ Central de Mediadores criado no guild {interaction.guild.id}")


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
            "`/setup` - Configurar cargo de mediador do servidor\n"
            "`/central-apostado` - Criar painel do Central de Mediadores"
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
            # Tenta reutilizar convites existentes primeiro
            invites = await guild.invites()
            if invites:
                invite_link = invites[0].url
            else:
                # Tenta criar convite - busca o melhor canal possível
                channels_to_try = [
                    guild.system_channel,  # Canal de sistema primeiro
                    *guild.text_channels   # Depois tenta outros canais
                ]

                for channel in channels_to_try:
                    if not channel:
                        continue
                    try:
                        invite = await channel.create_invite(
                            max_age=0,      # Nunca expira
                            max_uses=0,     # Usos ilimitados
                            unique=False    # Reutiliza se já existir
                        )
                        invite_link = invite.url
                        break
                    except discord.Forbidden:
                        continue  # Tenta próximo canal
                    except Exception:
                        continue  # Tenta próximo canal
        except discord.Forbidden:
            invite_link = "Bot sem permissão 'Criar Convite'"
        except Exception as e:
            invite_link = f"Erro: {str(e)[:50]}"

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


@bot.tree.command(name="aviso-de-atualizacao", description="[CRIADOR] Avisar sobre atualização do bot em todos os servidores")
async def aviso_de_atualizacao(interaction: discord.Interaction):
    """Envia aviso de atualização em todos os servidores"""
    if not is_creator(interaction.user.id):
        await interaction.response.send_message("❌ Apenas o criador do bot pode usar este comando.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    sent_count = 0
    failed_count = 0

    for guild in bot.guilds:
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

            if not channel:
                log(f"⚠️ Nenhum canal disponível em {guild.name}")
                failed_count += 1
                continue

            # Busca o cargo de mediador configurado
            mediator_role_id = db.get_mediator_role(guild.id)
            role_mention = None

            if mediator_role_id:
                # Tenta buscar o cargo de mediador configurado
                mediator_role = guild.get_role(mediator_role_id)
                if mediator_role:
                    role_mention = mediator_role.mention

            # Cria o embed (sem menção dentro)
            embed = discord.Embed(
                title="⚠️ Atualização do Bot em 5 Minutos",
                description=(
                    "O bot será atualizado em **5 minutos** e precisará reiniciar.\n\n"
                    "**Durante a atualização:**\n"
                    "• O bot ficará offline por alguns instantes\n"
                    "• Todas as filas atuais serão limpas\n"
                    "• Apostas ativas **NÃO** serão afetadas\n\n"
                    "**Após a atualização:**\n"
                    "• Será necessário recriar os painéis de fila\n"
                    "• Use `/preset-filas` ou `/mostrar-fila`\n\n"
                    "Pedimos desculpas pelo inconveniente!"
                ),
                color=0xFF9900
            )
            embed.set_footer(text=CREATOR_FOOTER)

            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)

            # Envia a mensagem - menciona o cargo FORA do embed se configurado
            if role_mention:
                # Marca o cargo ANTES do embed
                await channel.send(content=role_mention, embed=embed)
            else:
                # Sem menção se não houver cargo configurado
                await channel.send(embed=embed)

            sent_count += 1
            log(f"✅ Aviso enviado para {guild.name} (canal: {channel.name})")

            # Delay para evitar rate limit
            await asyncio.sleep(1)

        except Exception as e:
            log(f"❌ Erro ao enviar aviso para {guild.name}: {e}")
            failed_count += 1
            continue

    # Resposta final
    result_embed = discord.Embed(
        title="✅ Avisos Enviados",
        description="Aviso de atualização enviado para os servidores",
        color=0x00FF00
    )
    result_embed.add_field(name="Enviados", value=str(sent_count), inline=True)
    result_embed.add_field(name="Falharam", value=str(failed_count), inline=True)
    result_embed.add_field(name="Total", value=str(len(bot.guilds)), inline=True)
    result_embed.set_footer(text=CREATOR_FOOTER)

    await interaction.followup.send(embed=result_embed, ephemeral=True)
    log(f"📢 Avisos de atualização enviados: {sent_count}/{len(bot.guilds)} servidores")


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


# ===== SERVIDOR HTTP PARA HEALTHCHECK (Railway/Railway) =====
# Middleware para filtrar logs de health checks
@web.middleware
async def filter_health_check_logs(request, handler):
    """Middleware que evita logar health checks"""
    # Paths que não devem gerar logs
    silent_paths = ['/ping', '/health', '/']

    # User-agents que não devem gerar logs
    silent_agents = ['Consul Health Check', 'UptimeRobot']

    # Verificar se é uma requisição silenciosa
    is_silent = (
        request.path in silent_paths or
        any(agent in request.headers.get('User-Agent', '') for agent in silent_agents)
    )

    # Processar requisição normalmente
    response = await handler(request)

    # Não logar se for health check
    if is_silent:
        return response

    # Logar apenas requisições importantes
    log(f"{request.method} {request.path} - {response.status}")
    return response

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
    """Endpoint de healthcheck para Railway/Railway"""
    bot_status = "online" if bot.is_ready() else "starting"
    return web.Response(
        text=f"Bot Status: {bot_status}\nUptime: OK",
        status=200,
        headers={'Content-Type': 'text/plain'}
    )

async def ping(request):
    """Endpoint simples de ping"""
    return web.Response(text="pong", status=200)

async def serve_static(request):
    """Serve arquivos estáticos (imagens, CSS, etc)"""
    filename = request.match_info.get('filename', '')
    file_path = os.path.join(os.path.dirname(__file__), 'static', filename)

    if not os.path.exists(file_path):
        return web.Response(text="File not found", status=404)

    # Determina o content type baseado na extensão
    content_type = 'application/octet-stream'
    if filename.endswith('.jpg') or filename.endswith('.jpeg'):
        content_type = 'image/jpeg'
    elif filename.endswith('.png'):
        content_type = 'image/png'
    elif filename.endswith('.gif'):
        content_type = 'image/gif'
    elif filename.endswith('.css'):
        content_type = 'text/css'
    elif filename.endswith('.js'):
        content_type = 'application/javascript'

    with open(file_path, 'rb') as f:
        return web.Response(body=f.read(), content_type=content_type)

async def start_web_server():
    """Inicia servidor HTTP para healthcheck e dashboard"""
    app = web.Application(middlewares=[filter_health_check_logs])
    app.router.add_get('/', dashboard)
    app.router.add_get('/health', health_check)
    app.router.add_get('/ping', ping)
    app.router.add_get('/{filename}', serve_static)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv('PORT', 5000))
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
    log(f"🤖 Usuário: {bot.user}")
    log(f"📛 Nome: {bot.user.name}")
    log(f"🆔 ID: {bot.user.id}")
    log(f"🌐 Servidores: {len(bot.guilds)}")
    
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


async def run_bot_single():
    """Roda um único bot (modo econômico)"""
    token = os.getenv("TOKEN") or os.getenv("DISCORD_TOKEN") or os.getenv("TOKEN_1") or ""
    if not token:
        raise Exception("Configure DISCORD_TOKEN nas variáveis de ambiente.")

    log("🤖 Modo econômico: Iniciando 1 bot...")
    await bot.start(token, reconnect=True)

def create_bot_instance():
    """Cria uma nova instância do bot com a mesma configuração"""
    return commands.Bot(
        command_prefix="!",
        intents=intents,
        chunk_guilds_at_startup=False,
        member_cache_flags=discord.MemberCacheFlags.none(),
        max_messages=10
    )

async def run_bot_with_token():
    """Inicia o bot com o(s) token(s) disponível(eis)"""
    # Buscar tokens nas variáveis de ambiente
    # Prioridade: Se tem TOKEN ou DISCORD_TOKEN, usa apenas 1 bot
    if os.getenv("TOKEN") or os.getenv("DISCORD_TOKEN"):
        token = os.getenv("TOKEN") or os.getenv("DISCORD_TOKEN")
        log("🤖 Iniciando bot Discord (token único via TOKEN/DISCORD_TOKEN)...")
        await bot.start(token, reconnect=True)
        return
    
    # Caso contrário, verifica TOKEN_1 e TOKEN_2
    token1 = os.getenv("TOKEN_1")
    token2 = os.getenv("TOKEN_2")
    
    if not token1:
        raise Exception("Configure TOKEN, DISCORD_TOKEN ou TOKEN_1 nas variáveis de ambiente.")
    
    # Se só tem TOKEN_1, roda 1 bot
    if not token2:
        log("🤖 Iniciando bot Discord (token único via TOKEN_1)...")
        await bot.start(token1, reconnect=True)
        return
    
    # Se tem TOKEN_1 e TOKEN_2, roda 2 bots em paralelo
    log("🤖 Detectados 2 tokens (TOKEN_1 e TOKEN_2) - iniciando 2 bots em paralelo...")
    
    # Criar segunda instância do bot
    bot2 = create_bot_instance()
    
    # Registrar todos os comandos no bot2
    log("📋 Registrando comandos no segundo bot...")
    register_all_commands(bot2)
    log(f"✅ Comandos registrados no bot2")
    
    # Criar event handler on_ready específico para bot2
    @bot2.event
    async def on_ready():
        log("=" * 50)
        log("✅ BOT #2 CONECTADO AO DISCORD!")
        log("=" * 50)
        log(f'👤 Usuário: {bot2.user}')
        log(f'📛 Nome: {bot2.user.name}')
        log(f'🆔 ID: {bot2.user.id}')
        log(f'🌐 Servidores: {len(bot2.guilds)}')
        
        # Sincronizar comandos do bot2
        try:
            log("🔄 Bot #2: Sincronizando comandos slash...")
            synced = await bot2.tree.sync(guild=None)
            log(f'✅ Bot #2: {len(synced)} comandos sincronizados')
            for cmd in synced:
                log(f'  - /{cmd.name}')
        except Exception as e:
            log(f'⚠️ Bot #2: Erro ao sincronizar comandos: {e}')
    
    # Adicionar views persistentes para bot2
    bot2.add_view(QueueButton(mode="", bet_value=0, mediator_fee=0, currency_type="sonhos"))
    bot2.add_view(TeamQueueButton(mode="2v2-misto", bet_value=0, mediator_fee=0, currency_type="sonhos"))
    bot2.add_view(Unified1v1PanelView())
    bot2.add_view(Unified2v2PanelView())
    bot2.add_view(ConfirmPaymentButton(bet_id=""))
    bot2.add_view(AcceptMediationButton(bet_id=""))
    
    # Funções auxiliares para iniciar cada bot
    async def start_bot1():
        log("🤖 Bot #1: Conectando ao Discord...")
        await bot.start(token1, reconnect=True)
    
    async def start_bot2():
        log("🤖 Bot #2: Conectando ao Discord...")
        await bot2.start(token2, reconnect=True)
    
    # Rodar ambos em paralelo
    log("🚀 Iniciando ambos os bots...")
    await asyncio.gather(start_bot1(), start_bot2())

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

            # Iniciar bot
            log("🚀 Iniciando bot Discord...")
            await run_bot_with_token()

        asyncio.run(run_flyio())

    elif IS_RAILWAY:
        log("Iniciando bot no Railway com servidor HTTP...")

        async def run_all():
            # Iniciar servidor web primeiro
            await start_web_server()
            await asyncio.sleep(1)

            # Iniciar bot
            await run_bot_with_token()

        asyncio.run(run_all())
    
    elif IS_RENDER:
        log("=" * 60)
        log("🎨  INICIANDO NO RENDER")
        log("=" * 60)
        log(f"📍 Service: {os.getenv('RENDER_SERVICE_NAME', 'N/A')}")
        log(f"🌍 Region: {os.getenv('RENDER_REGION', 'N/A')}")
        log("💡 Para múltiplos bots: crie múltiplos Web Services no Render")
        log("💡 Cada serviço usa um TOKEN diferente")
        log("💡 Todos compartilham o mesmo DATABASE_URL")
        
        async def run_render():
            # Iniciar servidor web primeiro
            log("📡 Iniciando servidor HTTP...")
            await start_web_server()
            await asyncio.sleep(1)
            log("✅ Servidor HTTP rodando")
            
            # Iniciar bot
            log("🚀 Iniciando bot Discord...")
            await run_bot_with_token()
        
        asyncio.run(run_render())
    
    else:
        log("Iniciando bot no Replit/Local com servidor HTTP...")

        async def run_replit():
            # Iniciar servidor web primeiro
            await start_web_server()
            await asyncio.sleep(1)
            # Iniciar bot
            await run_bot_with_token()

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
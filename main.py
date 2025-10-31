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

# Função para logging com flush automático (necessário para Fly.io)
def log(message):
    print(message, flush=True)

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
    max_messages=50  # Cache mínimo de mensagens (padrão é 1000)
)
db = Database()

MODES = ["1v1-misto", "1v1-mob", "2v2-misto", "2v2-mob"]
ACTIVE_BETS_CATEGORY = "💰 Apostas Ativas"
EMBED_COLOR = 0x5865F2
CREATOR_FOOTER = "Bot feito por SKplay. Todos os direitos reservados | Criador: <@1339336477661724674>"
ALLOWED_ROLE_ID = 1393707608254320671  # Cargo que pode criar filas sem ser admin
ALLOWED_USER_ID = 1309895241851207681  # Usuário com permissões especiais

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

    async def update_queue_message(self, interaction: discord.Interaction):
        """Atualiza a mensagem da fila com os jogadores atuais"""
        if not self.message_id:
            return

        try:
            message = await interaction.channel.fetch_message(self.message_id)
            queue = db.get_queue(self.queue_id)

            # Busca os nomes dos jogadores na fila
            player_names = []
            for user_id in queue:
                try:
                    member = await interaction.guild.fetch_member(user_id)
                    player_names.append(member.mention)
                except:
                    player_names.append(f"<@{user_id}>")

            players_text = "\n".join(player_names) if player_names else "Nenhum jogador na fila"

            embed = discord.Embed(
                title=self.mode.replace('-', ' ').title(),
                color=EMBED_COLOR
            )

            embed.add_field(name="Valor", value=f"R$ {self.bet_value:.2f}".replace('.', ','), inline=True)
            embed.add_field(name="Fila", value=players_text if players_text != "Nenhum jogador na fila" else "Vazio", inline=True)
            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)
            embed.set_footer(text=CREATOR_FOOTER)

            await message.edit(embed=embed)
        except Exception as e:
            log(f"Erro ao atualizar mensagem da fila: {e}")

    @discord.ui.button(label='Entrar na Fila', style=discord.ButtonStyle.blurple, row=0, custom_id='persistent:join_queue')
    async def join_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id

        if db.is_user_in_active_bet(user_id):
            await interaction.response.send_message(
                "Você já está em uma aposta ativa. Finalize ela antes de entrar em outra fila.",
                ephemeral=True
            )
            return

        # Recarrega a fila para garantir que está atualizada
        queue = db.get_queue(self.queue_id)

        if user_id in queue:
            await interaction.response.send_message(
                "Você já está nesta fila.",
                ephemeral=True
            )
            return

        # Adiciona à fila ANTES de responder
        db.add_to_queue(self.queue_id, user_id)
        queue = db.get_queue(self.queue_id)

        # Responde ao usuário
        embed = discord.Embed(
            title="✅ Entrou na fila",
            description=f"{self.mode.replace('-', ' ').title()} - {len(queue)}/2",
            color=EMBED_COLOR
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=CREATOR_FOOTER)

        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Atualiza a mensagem principal IMEDIATAMENTE
        try:
            message = await interaction.channel.fetch_message(self.message_id)

            # Busca os nomes dos jogadores na fila
            player_names = []
            for uid in queue:
                try:
                    member = await interaction.guild.fetch_member(uid)
                    player_names.append(member.mention)
                except:
                    player_names.append(f"<@{uid}>")

            players_text = "\n".join(player_names) if player_names else "Vazio"

            embed_update = discord.Embed(
                title=self.mode.replace('-', ' ').title(),
                color=EMBED_COLOR
            )
            embed_update.add_field(name="Valor", value=f"R$ {self.bet_value:.2f}".replace('.', ','), inline=True)
            embed_update.add_field(name="Fila", value=players_text, inline=True)
            if interaction.guild.icon:
                embed_update.set_thumbnail(url=interaction.guild.icon.url)
            embed_update.set_footer(text=CREATOR_FOOTER)

            await message.edit(embed=embed_update)
        except Exception as e:
            log(f"Erro ao atualizar mensagem da fila: {e}")

        # Verifica se tem 2 jogadores para criar aposta
        if len(queue) >= 2:
            player1_id = queue[0]
            player2_id = queue[1]

            db.remove_from_queue(self.queue_id, player1_id)
            db.remove_from_queue(self.queue_id, player2_id)

            # Atualiza a mensagem após remover os jogadores
            await self.update_queue_message(interaction)

            await create_bet_channel(interaction.guild, self.mode, player1_id, player2_id, self.bet_value, self.mediator_fee)

    @discord.ui.button(label='Sair da Fila', style=discord.ButtonStyle.gray, row=0, custom_id='persistent:leave_queue')
    async def leave_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        queue = db.get_queue(self.queue_id)

        if user_id not in queue:
            await interaction.response.send_message(
                "Você não está nesta fila.",
                ephemeral=True
            )
            return

        db.remove_from_queue(self.queue_id, user_id)

        embed = discord.Embed(
            title="❌ Saiu da fila",
            color=EMBED_COLOR
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        embed.set_footer(text=CREATOR_FOOTER)

        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Atualiza a mensagem principal
        await self.update_queue_message(interaction)


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

            player1 = await interaction.guild.fetch_member(bet.player1_id)
            mediator = await interaction.guild.fetch_member(bet.mediator_id)

            embed = discord.Embed(
                title="✅ Pagamento Confirmado",
                description=player1.mention,
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

            player2 = await interaction.guild.fetch_member(bet.player2_id)
            mediator = await interaction.guild.fetch_member(bet.mediator_id)

            embed = discord.Embed(
                title="✅ Pagamento Confirmado",
                description=player2.mention,
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
            player1 = await interaction.guild.fetch_member(bet.player1_id)
            player2 = await interaction.guild.fetch_member(bet.player2_id)

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
            mediator = await interaction.guild.fetch_member(bet.mediator_id)
            await interaction.response.send_message(
                f"Esta aposta já tem um mediador: {mediator.mention}",
                ephemeral=True
            )
            return

        bet.mediator_id = interaction.user.id
        bet.mediator_pix = str(self.pix_key.value)
        db.update_active_bet(bet)

        player1 = await interaction.guild.fetch_member(bet.player1_id)
        player2 = await interaction.guild.fetch_member(bet.player2_id)

        embed = discord.Embed(
            title="Mediador Aceito",
            color=EMBED_COLOR
        )
        embed.add_field(name="Modo", value=bet.mode.replace("-", " ").title(), inline=True)
        embed.add_field(name="Jogadores", value=f"{player1.mention} vs {player2.mention}", inline=False)
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
        except:
            pass

        channel = interaction.guild.get_channel(bet.channel_id)
        if channel:
            perms = channel.overwrites_for(interaction.user)
            perms.read_messages = True
            perms.send_messages = True
            await channel.set_permissions(interaction.user, overwrite=perms)

            # Envia uma mensagem no canal mencionando os jogadores
            await channel.send(f"{player1.mention} {player2.mention} Um mediador aceitou a aposta! ✅")


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

        is_admin = interaction.user.guild_permissions.administrator
        has_allowed_role = discord.utils.get(interaction.user.roles, id=ALLOWED_ROLE_ID) is not None
        is_allowed_user = interaction.user.id == ALLOWED_USER_ID

        if not is_admin and not has_allowed_role and not is_allowed_user:
            await interaction.response.send_message("Apenas administradores, membros autorizados ou usuários especiais podem aceitar mediação.", ephemeral=True)
            return

        await interaction.response.send_modal(PixModal(self.bet_id))

    @discord.ui.button(label='Cancelar Aposta', style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        bet = db.get_active_bet(self.bet_id)

        if not bet:
            await interaction.response.send_message("Aposta não encontrada.", ephemeral=True)
            return

        # Verifica se é admin, tem o cargo permitido ou é o usuário especial
        is_admin = interaction.user.guild_permissions.administrator
        has_allowed_role = discord.utils.get(interaction.user.roles, id=ALLOWED_ROLE_ID) is not None
        is_allowed_user = interaction.user.id == ALLOWED_USER_ID

        if not is_admin and not has_allowed_role and not is_allowed_user:
            await interaction.response.send_message("Apenas administradores, membros autorizados ou usuários especiais podem cancelar apostas.", ephemeral=True)
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

        await asyncio.sleep(10)

        try:
            await interaction.channel.delete()
        except:
            pass


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

                                    guild = channel.guild
                                    team1_names = []
                                    for uid in team1_queue:
                                        try:
                                            member = await guild.fetch_member(uid)
                                            team1_names.append(member.mention)
                                        except:
                                            team1_names.append(f"<@{uid}>")

                                    team2_names = []
                                    for uid in team2_queue:
                                        try:
                                            member = await guild.fetch_member(uid)
                                            team2_names.append(member.mention)
                                        except:
                                            team2_names.append(f"<@{uid}>")

                                    team1_text = "\n".join(team1_names) if team1_names else "Nenhum jogador"
                                    team2_text = "\n".join(team2_names) if team2_names else "Nenhum jogador"

                                    embed = discord.Embed(
                                        title=mode.replace('-', ' ').title(),
                                        color=EMBED_COLOR
                                    )
                                    embed.add_field(name="Valor", value=f"R$ {bet_value:.2f}".replace('.', ','), inline=True)
                                    embed.add_field(name="Time 1", value=team1_text, inline=True)
                                    embed.add_field(name="Time 2", value=team2_text, inline=True)
                                    if guild.icon:
                                        embed.set_thumbnail(url=guild.icon.url)
                                else:
                                    queue = db.get_queue(queue_id)

                                    guild = channel.guild
                                    player_names = []
                                    for uid in queue:
                                        try:
                                            member = await guild.fetch_member(uid)
                                            player_names.append(member.mention)
                                        except:
                                            player_names.append(f"<@{uid}>")

                                    players_text = "\n".join(player_names) if player_names else "Vazio"

                                    embed = discord.Embed(
                                        title=mode.replace('-', ' ').title(),
                                        color=EMBED_COLOR
                                    )
                                    embed.add_field(name="Valor", value=f"R$ {bet_value:.2f}".replace('.', ','), inline=True)
                                    embed.add_field(name="Fila", value=players_text, inline=True)
                                    if guild.icon:
                                        embed.set_thumbnail(url=guild.icon.url)

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
    print(f'Bot conectado como {bot.user}')
    print(f'Nome: {bot.user.name}')
    print(f'ID: {bot.user.id}')
    try:
        synced = await bot.tree.sync()
        print(f'{len(synced)} comandos sincronizados')
    except Exception as e:
        print(f'Erro ao sincronizar comandos: {e}')

    # Registrar views persistentes (para botões não expirarem)
    log('📋 Registrando views persistentes...')
    
    # Registrar QueueButton como view persistente (custom_id dinâmico)
    # Isso garante que os botões funcionem mesmo após reiniciar o bot
    bot.add_view(QueueButton(mode="1v1-misto", bet_value=0, mediator_fee=0))
    bot.add_view(ConfirmPaymentButton(bet_id=""))
    # AcceptMediationButton e DeclareWinnerButton não têm timeout=None nos botões cancel
    # então não podem ser registradas como persistentes
    
    log('✅ Views persistentes registradas')

    # Inicia a tarefa de limpeza automática de filas
    bot.loop.create_task(cleanup_expired_queues())





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
    # Verifica se é admin, tem o cargo permitido ou é o usuário especial
    is_admin = interaction.user.guild_permissions.administrator
    has_allowed_role = discord.utils.get(interaction.user.roles, id=ALLOWED_ROLE_ID) is not None
    is_allowed_user = interaction.user.id == ALLOWED_USER_ID

    if not is_admin and not has_allowed_role and not is_allowed_user:
        await interaction.response.send_message(
            f"❌ Você precisa ser administrador ou ter o cargo <@&{ALLOWED_ROLE_ID}> para usar este comando.",
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

    # Salva a informação da fila para o sistema de limpeza automática
    queue_id = f"{mode}_{message.id}"
    queue_messages[queue_id] = (interaction.channel.id, message.id, mode, valor)






async def create_bet_channel(guild: discord.Guild, mode: str, player1_id: int, player2_id: int, bet_value: float, mediator_fee: float):
    if db.is_user_in_active_bet(player1_id) or db.is_user_in_active_bet(player2_id):
        log(f"Um dos jogadores já está em uma aposta ativa. Abortando criação.")
        return

    db.remove_from_all_queues(player1_id)
    db.remove_from_all_queues(player2_id)

    try:
        player1 = await guild.fetch_member(player1_id)
        player2 = await guild.fetch_member(player2_id)

        category = discord.utils.get(guild.categories, name=ACTIVE_BETS_CATEGORY)
        if not category:
            category = await guild.create_category(ACTIVE_BETS_CATEGORY)

        channel_name = f"aposta-{player1.name}-vs-{player2.name}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            player1: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            player2: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        channel = await category.create_text_channel(name=channel_name, overwrites=overwrites)

        bet_id = f"{player1_id}_{player2_id}_{int(datetime.now().timestamp())}"
        bet = Bet(
            bet_id=bet_id,
            mode=mode,
            player1_id=player1_id,
            player2_id=player2_id,
            mediator_id=0,
            channel_id=channel.id,
            bet_value=bet_value,
            mediator_fee=mediator_fee
        )
        db.add_active_bet(bet)
    except Exception as e:
        log(f"Erro ao criar canal de aposta: {e}")
        db.add_to_queue(mode, player1_id)
        db.add_to_queue(mode, player2_id)
        return

    admin_role = discord.utils.get(guild.roles, permissions=discord.Permissions(administrator=True))
    admin_mention = admin_role.mention if admin_role else "@Administradores"

    embed = discord.Embed(
        title="Aposta - Aguardando Mediador",
        description=admin_mention,
        color=EMBED_COLOR
    )
    embed.add_field(name="Modo", value=mode.replace("-", " ").title(), inline=True)
    embed.add_field(name="Valor", value=f"R$ {bet_value:.2f}".replace('.', ','), inline=True)
    embed.add_field(name="Taxa", value=f"R$ {mediator_fee:.2f}".replace('.', ','), inline=True)
    embed.add_field(name="Jogadores", value=f"{player1.mention} vs {player2.mention}", inline=False)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text=CREATOR_FOOTER)

    view = AcceptMediationButton(bet_id)

    await channel.send(content=f"{player1.mention} {player2.mention} Aposta criada! Aguardando mediador... {admin_mention}", embed=embed, view=view)


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
            "Este canal não é uma aposta ativa.",
            ephemeral=True
        )
        return

    if interaction.user.id != bet.mediator_id:
        await interaction.response.send_message(
            "Apenas o mediador pode finalizar esta aposta.",
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

    player1 = await interaction.guild.fetch_member(bet.player1_id)
    player2 = await interaction.guild.fetch_member(bet.player2_id)
    loser = player1 if vencedor.id == bet.player2_id else player2

    embed = discord.Embed(
        title="🏆 Vencedor",
        description=vencedor.mention,
        color=EMBED_COLOR
    )
    embed.add_field(name="Modo", value=bet.mode.replace("-", " ").title(), inline=True)
    embed.add_field(name="Perdedor", value=loser.mention, inline=True)
    embed.set_footer(text=CREATOR_FOOTER)

    await interaction.response.send_message(embed=embed)

    db.finish_bet(bet)

    import asyncio
    await asyncio.sleep(10)

    try:
        await interaction.channel.delete()
    except:
        pass


@bot.tree.command(name="cancelar-aposta", description="[MEDIADOR] Cancelar uma aposta em andamento")
async def cancelar_aposta(interaction: discord.Interaction):
    bet = db.get_bet_by_channel(interaction.channel_id)

    if not bet:
        await interaction.response.send_message(
            "Este canal não é uma aposta ativa.",
            ephemeral=True
        )
        return

    if interaction.user.id != bet.mediator_id:
        await interaction.response.send_message(
            "Apenas o mediador pode cancelar esta aposta.",
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
        await interaction.channel.delete()
    except:
        pass


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
            channel = interaction.guild.get_channel(bet.channel_id)
            if channel:
                await channel.delete()
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
        name="Como Funciona",
        value=(
            "1. Moderadores criam filas com `/mostrar-fila`\n"
            "2. Clique no botão 'Entrar na Fila' da mensagem\n"
            "3. Quando encontrar outro jogador, um canal privado será criado\n"
            "4. Envie o valor da aposta para o mediador\n"
            "5. Confirme com `/confirmar-pagamento`\n"
            "6. Jogue a partida\n"
            "7. O mediador declara o vencedor com `/finalizar-aposta`"
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

    log("🚀 Iniciando bot com servidor HTTP...")

    # Iniciar servidor web ANTES do bot
    web_server = await start_web_server()

    # Aguardar um pouco para o servidor estar pronto
    await asyncio.sleep(1)

    log("🤖 Conectando bot ao Discord...")

    # Iniciar bot Discord
    try:
        await bot.start(token, reconnect=True)
    except Exception as e:
        log(f"❌ Erro ao iniciar bot: {e}")
        raise


try:
    if IS_FLYIO:
        log("Iniciando bot no Fly.io com servidor HTTP...")
    elif IS_RAILWAY:
        log("Iniciando bot no Railway com servidor HTTP...")
    else:
        log("Iniciando bot no Replit/Local...")

    # Rodar bot com servidor web em ambientes de produção
    if IS_FLYIO or IS_RAILWAY:
        asyncio.run(run_bot_with_webserver())
    else:
        # No Replit/Local, rodar apenas o bot
        token = os.getenv("DISCORD_TOKEN") or os.getenv("TOKEN") or ""
        if token == "":
            raise Exception("Por favor, adicione seu token do Discord nas variáveis de ambiente (DISCORD_TOKEN).")
        bot.run(token)

except discord.HTTPException as e:
    if e.status == 429:
        log("O Discord bloqueou a conexão por excesso de requisições")
        log("Veja: https://stackoverflow.com/questions/66724687/in-discord-py-how-to-solve-the-error-for-toomanyrequests")
    else:
        raise e
except Exception as e:
    log(f"Erro ao iniciar o bot: {e}")
    if IS_RAILWAY:
        # No Railway, queremos saber exatamente o que deu errado
        import traceback
        traceback.print_exc()
        raise
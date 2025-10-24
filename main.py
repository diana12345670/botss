import os
import discord
from discord import app_commands
from discord.ext import commands
import random
import asyncio
from datetime import datetime
from models.bet import Bet
from utils.database import Database

# Detectar ambiente de execução
IS_FLYIO = os.getenv("FLY_APP_NAME") is not None
IS_RAILWAY = os.getenv("RAILWAY_ENVIRONMENT") is not None or os.getenv("RAILWAY_STATIC_URL") is not None

if IS_FLYIO:
    print("✈️ Detectado ambiente Fly.io")
elif IS_RAILWAY:
    print("🚂 Detectado ambiente Railway")
else:
    print("💻 Detectado ambiente Replit/Local")

# Configuração otimizada de intents - apenas o necessário
intents = discord.Intents(
    guilds=True,           # Necessário para detectar servidores
    guild_messages=True,   # Necessário para mensagens
    members=True,          # Necessário para menções
    message_content=True   # Necessário para comandos
)
# Desabilitando eventos desnecessários para economizar RAM
intents.presences = False
intents.typing = False
intents.voice_states = False
intents.integrations = False
intents.webhooks = False
intents.invites = False
intents.emojis = False
intents.bans = False

bot = commands.Bot(command_prefix="!", intents=intents)
db = Database()

MODES = ["1v1-misto", "1v1-mob", "2v2-misto"]
ACTIVE_BETS_CATEGORY = "💰 Apostas Ativas"
EMBED_COLOR = 0x5865F2

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
        self.is_2v2 = "2v2" in mode

        # Remove o botão "Entrar na Fila" se for 2v2
        if self.is_2v2:
            self.remove_item(self.join_queue_button)
        else:
            # Remove os botões de time se for 1v1
            self.remove_item(self.join_team1_button)
            self.remove_item(self.join_team2_button)

    async def update_queue_message(self, interaction: discord.Interaction):
        """Atualiza a mensagem da fila com os jogadores atuais"""
        if not self.message_id:
            return

        try:
            message = await interaction.channel.fetch_message(self.message_id)

            if self.is_2v2:
                team1_queue = db.get_queue(f"{self.queue_id}_team1")
                team2_queue = db.get_queue(f"{self.queue_id}_team2")

                # Time 1
                team1_names = []
                for user_id in team1_queue:
                    try:
                        member = await interaction.guild.fetch_member(user_id)
                        team1_names.append(member.mention)
                    except:
                        team1_names.append(f"<@{user_id}>")

                # Time 2
                team2_names = []
                for user_id in team2_queue:
                    try:
                        member = await interaction.guild.fetch_member(user_id)
                        team2_names.append(member.mention)
                    except:
                        team2_names.append(f"<@{user_id}>")

                team1_text = "\n".join(team1_names) if team1_names else "Nenhum jogador"
                team2_text = "\n".join(team2_names) if team2_names else "Nenhum jogador"

                embed = discord.Embed(
                    title=self.mode.replace('-', ' ').title(),
                    color=EMBED_COLOR
                )

                embed.add_field(name="Valor", value=f"R$ {self.bet_value:.2f}".replace('.', ','), inline=True)
                embed.add_field(name="Time 1", value=team1_text, inline=True)
                embed.add_field(name="Time 2", value=team2_text, inline=True)
                if interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)
            else:
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

            await message.edit(embed=embed)
        except:
            pass

    @discord.ui.button(label='Entrar na Fila', style=discord.ButtonStyle.blurple, row=0)
    async def join_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Este botão não aparece no modo 2v2
        if self.is_2v2:
            return

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

        db.add_to_queue(self.queue_id, user_id)
        queue = db.get_queue(self.queue_id)

        embed = discord.Embed(
            title="✅ Entrou na fila",
            description=f"{self.mode.replace('-', ' ').title()} - {len(queue)}/2",
            color=EMBED_COLOR
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        await interaction.response.send_message(embed=embed, ephemeral=True)

        # Atualiza a mensagem principal
        await self.update_queue_message(interaction)

        if len(queue) >= 2:
            player1_id = queue[0]
            player2_id = queue[1]

            db.remove_from_queue(self.queue_id, player1_id)
            db.remove_from_queue(self.queue_id, player2_id)

            # Atualiza a mensagem após remover os jogadores
            await self.update_queue_message(interaction)

            await create_bet_channel(interaction.guild, self.mode, player1_id, player2_id, self.bet_value, self.mediator_fee)

    @discord.ui.button(label='Sair da Fila', style=discord.ButtonStyle.gray, row=0)
    async def leave_queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id

        if self.is_2v2:
            team1_queue_id = f"{self.queue_id}_team1"
            team2_queue_id = f"{self.queue_id}_team2"

            team1_queue = db.get_queue(team1_queue_id)
            team2_queue = db.get_queue(team2_queue_id)

            if user_id in team1_queue:
                db.remove_from_queue(team1_queue_id, user_id)
                embed = discord.Embed(
                    title="❌ Saiu - Time 1",
                    color=EMBED_COLOR
                )
                if interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                await self.update_queue_message(interaction)
                return
            elif user_id in team2_queue:
                db.remove_from_queue(team2_queue_id, user_id)
                embed = discord.Embed(
                    title="❌ Saiu - Time 2",
                    color=EMBED_COLOR
                )
                if interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                await self.update_queue_message(interaction)
                return
            else:
                await interaction.response.send_message(
                    "Você não está em nenhum time.",
                    ephemeral=True
                )
                return
        else:
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

            await interaction.response.send_message(embed=embed, ephemeral=True)

            # Atualiza a mensagem principal
            await self.update_queue_message(interaction)

    @discord.ui.button(label='Entrar no Time 1', style=discord.ButtonStyle.blurple, row=0)
    async def join_team1_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_2v2:
            await interaction.response.send_message(
                "Este botão é exclusivo do modo 2v2.",
                ephemeral=True
            )
            return

        user_id = interaction.user.id

        if db.is_user_in_active_bet(user_id):
            await interaction.response.send_message(
                "Você já está em uma aposta ativa. Finalize ela antes de entrar em outra fila.",
                ephemeral=True
            )
            return

        team1_queue_id = f"{self.queue_id}_team1"
        team2_queue_id = f"{self.queue_id}_team2"

        team1_queue = db.get_queue(team1_queue_id)
        team2_queue = db.get_queue(team2_queue_id)

        if user_id in team1_queue:
            await interaction.response.send_message(
                "Você já está no Time 1.",
                ephemeral=True
            )
            return

        if user_id in team2_queue:
            await interaction.response.send_message(
                "Você já está no Time 2. Saia primeiro para entrar no Time 1.",
                ephemeral=True
            )
            return

        if len(team1_queue) >= 2:
            await interaction.response.send_message(
                "O Time 1 já está completo.",
                ephemeral=True
            )
            return

        db.add_to_queue(team1_queue_id, user_id)
        team1_queue = db.get_queue(team1_queue_id)

        embed = discord.Embed(
            title="✅ Time 1",
            description=f"{self.mode.replace('-', ' ').title()} - {len(team1_queue)}/2",
            color=EMBED_COLOR
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.update_queue_message(interaction)

        # Verifica se ambos os times estão completos
        team2_queue = db.get_queue(team2_queue_id)
        if len(team1_queue) == 2 and len(team2_queue) == 2:
            await self.create_2v2_match(interaction.guild, team1_queue, team2_queue)

    @discord.ui.button(label='Entrar no Time 2', style=discord.ButtonStyle.blurple, row=0)
    async def join_team2_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.is_2v2:
            await interaction.response.send_message(
                "Este botão é exclusivo do modo 2v2.",
                ephemeral=True
            )
            return

        user_id = interaction.user.id

        if db.is_user_in_active_bet(user_id):
            await interaction.response.send_message(
                "Você já está em uma aposta ativa. Finalize ela antes de entrar em outra fila.",
                ephemeral=True
            )
            return

        team1_queue_id = f"{self.queue_id}_team1"
        team2_queue_id = f"{self.queue_id}_team2"

        team1_queue = db.get_queue(team1_queue_id)
        team2_queue = db.get_queue(team2_queue_id)

        if user_id in team2_queue:
            await interaction.response.send_message(
                "Você já está no Time 2.",
                ephemeral=True
            )
            return

        if user_id in team1_queue:
            await interaction.response.send_message(
                "Você já está no Time 1. Saia primeiro para entrar no Time 2.",
                ephemeral=True
            )
            return

        if len(team2_queue) >= 2:
            await interaction.response.send_message(
                "O Time 2 já está completo.",
                ephemeral=True
            )
            return

        db.add_to_queue(team2_queue_id, user_id)
        team2_queue = db.get_queue(team2_queue_id)

        embed = discord.Embed(
            title="✅ Time 2",
            description=f"{self.mode.replace('-', ' ').title()} - {len(team2_queue)}/2",
            color=EMBED_COLOR
        )
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.update_queue_message(interaction)

        # Verifica se ambos os times estão completos
        team1_queue = db.get_queue(team1_queue_id)
        if len(team1_queue) == 2 and len(team2_queue) == 2:
            await self.create_2v2_match(interaction.guild, team1_queue, team2_queue)

    async def create_2v2_match(self, guild: discord.Guild, team1_queue: list, team2_queue: list):
        """Cria uma partida 2v2 quando ambos os times estão completos"""
        team1_queue_id = f"{self.queue_id}_team1"
        team2_queue_id = f"{self.queue_id}_team2"

        # Remove todos os jogadores das filas
        for user_id in team1_queue:
            db.remove_from_queue(team1_queue_id, user_id)
        for user_id in team2_queue:
            db.remove_from_queue(team2_queue_id, user_id)

        # Cria o canal da aposta 2v2
        await create_2v2_bet_channel(guild, self.mode, team1_queue, team2_queue, self.bet_value, self.mediator_fee)


class ConfirmPaymentButton(discord.ui.View):
    def __init__(self, bet_id: str):
        super().__init__(timeout=None)
        self.bet_id = bet_id

    @discord.ui.button(label='Confirmar Pagamento', style=discord.ButtonStyle.green, emoji='💰')
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
            await interaction.response.send_message(embed=embed)

            try:
                await mediator.send(f"{player1.name} confirmou o pagamento na aposta {interaction.channel.mention}")
            except:
                pass

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

            try:
                await mediator.send(f"{player2.name} confirmou o pagamento na aposta {interaction.channel.mention}")
            except:
                pass
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

    @discord.ui.button(label='Aceitar Mediação', style=discord.ButtonStyle.green)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        bet = db.get_active_bet(self.bet_id)

        if not bet:
            await interaction.response.send_message("Aposta não encontrada.", ephemeral=True)
            return

        if bet.mediator_id != 0:
            await interaction.response.send_message("Esta aposta já tem um mediador.", ephemeral=True)
            return

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Apenas administradores podem aceitar mediação.", ephemeral=True)
            return

        await interaction.response.send_modal(PixModal(self.bet_id))


async def cleanup_expired_queues():
    """Tarefa em background que remove jogadores que ficaram muito tempo na fila"""
    await bot.wait_until_ready()
    print("🧹 Iniciando sistema de limpeza automática de filas (2 minutos)")
    
    while not bot.is_closed():
        try:
            # Busca jogadores expirados (mais de 2 minutos na fila)
            expired_players = db.get_expired_queue_players(timeout_minutes=2)
            
            if expired_players:
                print(f"🧹 Encontrados jogadores expirados em {len(expired_players)} filas")
                
                for queue_id, user_ids in expired_players.items():
                    # Remove cada jogador expirado
                    for user_id in user_ids:
                        db.remove_from_queue(queue_id, user_id)
                        print(f"⏱️ Removido usuário {user_id} da fila {queue_id} (timeout)")
                    
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
                            print(f"Erro ao atualizar mensagem da fila {queue_id}: {e}")
            
            # Aguarda 30 segundos antes de verificar novamente
            await asyncio.sleep(30)
            
        except Exception as e:
            print(f"Erro na limpeza de filas: {e}")
            await asyncio.sleep(30)


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
])
async def mostrar_fila(interaction: discord.Interaction, modo: app_commands.Choice[str], valor: float, taxa: float):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "Apenas moderadores podem usar este comando.",
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

    await interaction.response.send_message(embed=embed)

    # Pega a mensagem enviada para passar o ID para o botão
    message = await interaction.original_response()
    view = QueueButton(mode, valor, taxa, message.id)

    await message.edit(embed=embed, view=view)
    
    # Salva a informação da fila para o sistema de limpeza automática
    queue_id = f"{mode}_{message.id}"
    queue_messages[queue_id] = (interaction.channel.id, message.id, mode, valor)
    
    # Para 2v2, também salva as filas dos times
    if "2v2" in mode:
        queue_messages[f"{queue_id}_team1"] = (interaction.channel.id, message.id, mode, valor)
        queue_messages[f"{queue_id}_team2"] = (interaction.channel.id, message.id, mode, valor)








async def create_2v2_bet_channel(guild: discord.Guild, mode: str, team1: list, team2: list, bet_value: float, mediator_fee: float):
    """Cria um canal de aposta para modo 2v2"""
    # Verifica se algum jogador já está em aposta ativa
    for user_id in team1 + team2:
        if db.is_user_in_active_bet(user_id):
            print(f"Jogador {user_id} já está em uma aposta ativa. Abortando criação.")
            return

    # Remove todos os jogadores de todas as filas
    for user_id in team1 + team2:
        db.remove_from_all_queues(user_id)

    try:
        # Busca os membros
        team1_members = []
        team2_members = []

        for user_id in team1:
            member = await guild.fetch_member(user_id)
            team1_members.append(member)

        for user_id in team2:
            member = await guild.fetch_member(user_id)
            team2_members.append(member)

        category = discord.utils.get(guild.categories, name=ACTIVE_BETS_CATEGORY)
        if not category:
            category = await guild.create_category(ACTIVE_BETS_CATEGORY)

        channel_name = f"aposta-2v2-{team1_members[0].name}-{team1_members[1].name}-vs-{team2_members[0].name}-{team2_members[1].name}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        # Adiciona permissões para todos os jogadores
        for member in team1_members + team2_members:
            overwrites[member] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        channel = await category.create_text_channel(name=channel_name, overwrites=overwrites)

        # Cria ID da aposta com todos os jogadores
        bet_id = f"2v2_{team1[0]}_{team1[1]}_{team2[0]}_{team2[1]}_{int(datetime.now().timestamp())}"

        # Para 2v2, armazena como string separada por vírgula
        bet = Bet(
            bet_id=bet_id,
            mode=mode,
            player1_id=team1[0],  # Líder do time 1
            player2_id=team2[0],  # Líder do time 2
            mediator_id=0,
            channel_id=channel.id,
            bet_value=bet_value,
            mediator_fee=mediator_fee
        )

        # Adiciona campos customizados para 2v2
        bet_dict = bet.to_dict()
        bet_dict['team1'] = team1
        bet_dict['team2'] = team2
        bet_dict['is_2v2'] = True

        # Salva manualmente com campos extras
        data = db._load_data()
        data['active_bets'][bet_id] = bet_dict
        db._save_data(data)

    except Exception as e:
        print(f"Erro ao criar canal de aposta 2v2: {e}")
        return

    admin_role = discord.utils.get(guild.roles, permissions=discord.Permissions(administrator=True))
    admin_mention = admin_role.mention if admin_role else "@Administradores"

    team1_mentions = " ".join([m.mention for m in team1_members])
    team2_mentions = " ".join([m.mention for m in team2_members])

    embed = discord.Embed(
        title="Aposta 2v2 - Aguardando Mediador",
        description=admin_mention,
        color=EMBED_COLOR
    )
    embed.add_field(name="Modo", value=mode.replace("-", " ").title(), inline=True)
    embed.add_field(name="Valor/jogador", value=f"R$ {bet_value:.2f}".replace('.', ','), inline=True)
    embed.add_field(name="Taxa", value=f"R$ {mediator_fee:.2f}".replace('.', ','), inline=True)
    embed.add_field(name="Time 1", value=team1_mentions, inline=True)
    embed.add_field(name="Time 2", value=team2_mentions, inline=True)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    view = AcceptMediationButton(bet_id)

    all_mentions = " ".join([m.mention for m in team1_members + team2_members])
    await channel.send(content=f"{all_mentions} Aposta 2v2 criada! Aguardando mediador... {admin_mention}", embed=embed, view=view)


async def create_bet_channel(guild: discord.Guild, mode: str, player1_id: int, player2_id: int, bet_value: float, mediator_fee: float):
    if db.is_user_in_active_bet(player1_id) or db.is_user_in_active_bet(player2_id):
        print(f"Um dos jogadores já está em uma aposta ativa. Abortando criação.")
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
        print(f"Erro ao criar canal de aposta: {e}")
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

        try:
            await mediator.send(f"{player1.name} confirmou o pagamento na aposta {interaction.channel.mention}")
        except:
            pass

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

        try:
            await mediator.send(f"{player2.name} confirmou o pagamento na aposta {interaction.channel.mention}")
        except:
            pass
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
    embed.set_footer(text=f"Executado por {interaction.user.name}")
    if interaction.guild.icon:
        embed.set_thumbnail(url=interaction.guild.icon.url)

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

    await interaction.response.send_message(embed=embed)


try:
    token = os.getenv("DISCORD_TOKEN") or os.getenv("TOKEN") or ""
    if token == "":
        raise Exception("Por favor, adicione seu token do Discord nas variáveis de ambiente (DISCORD_TOKEN).")
    
    if IS_FLYIO:
        print("Iniciando bot no Fly.io...")
        # log_level=40 = ERROR apenas, economiza recursos
        bot.run(token, log_handler=None, log_level=40)
    elif IS_RAILWAY:
        print("Iniciando bot no Railway...")
        bot.run(token, log_handler=None, log_level=40)
    else:
        print("Iniciando bot no Replit/Local...")
        bot.run(token)
        
except discord.HTTPException as e:
    if e.status == 429:
        print("O Discord bloqueou a conexão por excesso de requisições")
        print("Veja: https://stackoverflow.com/questions/66724687/in-discord-py-how-to-solve-the-error-for-toomanyrequests")
    else:
        raise e
except Exception as e:
    print(f"Erro ao iniciar o bot: {e}")
    if IS_RAILWAY:
        # No Railway, queremos saber exatamente o que deu errado
        import traceback
        traceback.print_exc()
        raise
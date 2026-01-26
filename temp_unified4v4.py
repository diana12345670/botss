class Unified4v4PanelView(discord.ui.View):
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
        mob_base = self._base_qid("4v4-mob", message_id)
        misto_base = self._base_qid("4v4-misto", message_id)
        mob_t1, mob_t2 = self._team_qids(mob_base)
        misto_t1, misto_t2 = self._team_qids(misto_base)
        return [mob_t1, mob_t2, misto_t1, misto_t2]

    async def _update_panel(self, interaction: discord.Interaction, bet_value: float, currency_type: str, message_id_override: int | None = None):
        message_id = message_id_override or interaction.message.id

        mob_base = self._base_qid("4v4-mob", message_id)
        misto_base = self._base_qid("4v4-misto", message_id)
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

        embed_update = discord.Embed(title="Painel 4v4", color=EMBED_COLOR)
        embed_update.add_field(name="Valor", value=valor_formatado, inline=True)
        embed_update.add_field(name="Moeda", value=moeda_nome, inline=True)
        embed_update.add_field(
            name="📱 4v4 MOB",
            value=(
                f"T1 {len(mob1)}/4\n{render_team_mentions(mob1)}\n"
                f"T2 {len(mob2)}/4\n{render_team_mentions(mob2)}"
            ),
            inline=True
        )
        embed_update.add_field(
            name="💻 4v4 MISTO",
            value=(
                f"T1 {len(misto1)}/4\n{render_team_mentions(misto1)}\n"
                f"T2 {len(misto2)}/4\n{render_team_mentions(misto2)}"
            ),
            inline=True
        )
        if interaction.guild and interaction.guild.icon:
            embed_update.set_thumbnail(url=interaction.guild.icon.url)
        embed_update.set_footer(text=f"{interaction.guild.name if interaction.guild else ''}", icon_url=interaction.guild.icon.url if interaction.guild and interaction.guild.icon else None)

        try:
            message = await interaction.channel.fetch_message(message_id)
            await message.edit(embed=embed_update)
        except Exception as e:
            log(f"❌ Erro ao atualizar painel 4v4 unificado: {e}")

    async def _join_team(self, interaction: discord.Interaction, mode: str, team_number: int, message_id_override: int | None = None):
        target_message_id = message_id_override or interaction.message.id
        meta = db.get_panel_metadata(target_message_id)
        if not meta:
            await interaction.followup.send("⚠️ Dados do painel não encontrados. Recrie o painel.", ephemeral=True)
            return

        bet_value = float(meta['bet_value'])
        mediator_fee = float(meta['mediator_fee'])
        currency_type = meta.get('currency_type', 'sonhos')
        message_id = target_message_id

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
            if len(target_team) >= 4:
                await interaction.followup.send(f"Time {team_number} está cheio.", ephemeral=True)
                return

            db.add_to_queue(team1_qid if team_number == 1 else team2_qid, user_id)

        await self._update_panel(interaction, bet_value, currency_type, message_id_override=message_id)
        await self._try_create_bet_if_full(interaction, mode, base_qid, bet_value, mediator_fee, currency_type, panel_message_id=message_id)

    async def _try_create_bet_if_full(self, interaction: discord.Interaction, mode: str, base_qid: str, bet_value: float, mediator_fee: float, currency_type: str, panel_message_id: int):
        team1_qid, team2_qid = self._team_qids(base_qid)
        team1 = db.get_queue(team1_qid)
        team2 = db.get_queue(team2_qid)
        if len(team1) < 4 or len(team2) < 4:
            return

        db.set_queue(team1_qid, [])
        db.set_queue(team2_qid, [])

        await self._update_panel(interaction, bet_value, currency_type, message_id_override=panel_message_id)

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

    @discord.ui.button(label='📱 4v4 MOB', style=discord.ButtonStyle.red, row=0, custom_id='persistent:panel_4v4_mob')
    async def choose_4v4_mob(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Escolha o time para entrar em 4v4 MOB:",
            ephemeral=True,
            view=self._team_selector_view("4v4-mob", interaction.message.id)
        )

    @discord.ui.button(label='💻 4v4 MISTO', style=discord.ButtonStyle.red, row=0, custom_id='persistent:panel_4v4_misto')
    async def choose_4v4_misto(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Escolha o time para entrar em 4v4 MISTO:",
            ephemeral=True,
            view=self._team_selector_view("4v4-misto", interaction.message.id)
        )

    def _team_selector_view(self, mode: str, panel_message_id: int) -> discord.ui.View:
        parent = self

        class TeamSelector(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)

            @discord.ui.button(label="Time 1", style=discord.ButtonStyle.red, row=0)
            async def choose_team1(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.defer(ephemeral=True)
                await parent._join_team(interaction, mode, 1, message_id_override=panel_message_id)
                self.stop()

            @discord.ui.button(label="Time 2", style=discord.ButtonStyle.red, row=0)
            async def choose_team2(self, interaction: discord.Interaction, button: discord.ui.Button):
                await interaction.response.defer(ephemeral=True)
                await parent._join_team(interaction, mode, 2, message_id_override=panel_message_id)
                self.stop()

        return TeamSelector()

    @discord.ui.button(label='Sair', style=discord.ButtonStyle.gray, row=0, custom_id='persistent:panel_4v4_leave')
    async def leave_panel_4v4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        meta = await self._load_panel(interaction)
        if not meta:
            await interaction.followup.send("⚠️ Dados do painel não encontrados. Recrie o painel.", ephemeral=True)
            return

        user_id = interaction.user.id
        message_id = interaction.message.id
        removed = False

        mob_base = self._base_qid("4v4-mob", message_id)
        misto_base = self._base_qid("4v4-misto", message_id)

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


import os
import discord
from discord.ext import commands
from datetime import datetime, timezone

# =========================
# CONFIGURAÇÃO
# =========================

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
SUPPORT_ROLE_ID = int(os.getenv("SUPPORT_ROLE_ID", "0"))
TICKET_CATEGORY_ID = int(os.getenv("TICKET_CATEGORY_ID", "0"))

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix=".",
    intents=intents,
    help_command=None
)


# =========================
# EMBEDS
# =========================

def embed_base(titulo, descricao, cor=discord.Color.blurple()):
    return discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc)
    )


# =========================
# PAINEL DE TICKETS
# =========================

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Abrir ticket",
        emoji="🎫",
        style=discord.ButtonStyle.green,
        custom_id="zyron:abrir_ticket"
    )
    async def abrir_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        guild = interaction.guild

        if guild is None:
            await interaction.response.send_message(
                "Este botão só funciona dentro de um servidor.",
                ephemeral=True
            )
            return

        existente = discord.utils.get(
            guild.text_channels,
            name=f"ticket-{interaction.user.id}"
        )

        if existente:
            await interaction.response.send_message(
                f"Você já tem um ticket aberto: {existente.mention}",
                ephemeral=True
            )
            return

        categoria = guild.get_channel(TICKET_CATEGORY_ID) if TICKET_CATEGORY_ID else None
        cargo_suporte = guild.get_role(SUPPORT_ROLE_ID) if SUPPORT_ROLE_ID else None

        permissoes = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True
            )
        }

        if cargo_suporte:
            permissoes[cargo_suporte] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

        try:
            canal = await guild.create_text_channel(
                name=f"ticket-{interaction.user.id}",
                category=categoria if isinstance(
                    categoria, discord.CategoryChannel
                ) else None,
                overwrites=permissoes,
                topic=f"Ticket de {interaction.user} | ID: {interaction.user.id}"
            )

            view = FecharTicketView()

            await canal.send(
                f"Olá {interaction.user.mention}! 👋\n"
                "Explique seu problema e aguarde a equipe de suporte.",
                view=view
            )

            await interaction.response.send_message(
                f"Ticket criado: {canal.mention}",
                ephemeral=True
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "Não tenho permissão para criar tickets. "
                "Verifique as permissões do bot.",
                ephemeral=True
            )


class FecharTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Fechar ticket",
        emoji="🔒",
        style=discord.ButtonStyle.red,
        custom_id="zyron:fechar_ticket"
    )
    async def fechar_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        canal = interaction.channel
        guild = interaction.guild

        if not isinstance(canal, discord.TextChannel) or guild is None:
            await interaction.response.send_message(
                "Não foi possível fechar este ticket.",
                ephemeral=True
            )
            return

        cargo = guild.get_role(SUPPORT_ROLE_ID) if SUPPORT_ROLE_ID else None
        dono_id = None

        if canal.topic and "ID:" in canal.topic:
            try:
                dono_id = int(canal.topic.split("ID:")[-1].strip())
            except ValueError:
                dono_id = None

        eh_dono = interaction.user.id == dono_id
        eh_suporte = cargo is not None and cargo in interaction.user.roles
        eh_admin = interaction.user.guild_permissions.manage_channels

        if not (eh_dono or eh_suporte or eh_admin):
            await interaction.response.send_message(
                "Somente o dono do ticket, a equipe de suporte "
                "ou um administrador pode fechá-lo.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "🔒 Ticket será fechado em 5 segundos."
        )

        import asyncio
        await asyncio.sleep(5)

        try:
            await canal.delete(reason=f"Ticket fechado por {interaction.user}")
        except discord.Forbidden:
            pass


# =========================
# EVENTOS
# =========================

@bot.event
async def on_ready():
    bot.add_view(TicketView())
    bot.add_view(FecharTicketView())

    print(f"ZYRON SENSI conectado como {bot.user}")
    print(f"Prefixo dos comandos: .")


# =========================
# .p - PAINEL
# =========================

@bot.command(name="p")
@commands.guild_only()
@commands.has_permissions(manage_guild=True)
async def painel(ctx):
    embed = embed_base(
        "🎫 ZYRON SENSI | SUPORTE",
        "Precisa de ajuda? Clique no botão abaixo para abrir um ticket.\n\n"
        "• Atendimento individual\n"
        "• Suporte da equipe\n"
        "• Um ticket por usuário"
    )
    await ctx.send(embed=embed, view=TicketView())


# =========================
# .r - REGRAS
# =========================

@bot.command(name="r")
@commands.guild_only()
async def regras(ctx):
    embed = embed_base(
        "📜 REGRAS DO SERVIDOR",
        "**1.** Respeite todos os membros.\n"
        "**2.** Não faça spam ou flood.\n"
        "**3.** Não divulgue links sem autorização.\n"
        "**4.** Não abuse dos canais de suporte.\n"
        "**5.** Siga as orientações da equipe.\n\n"
        "O descumprimento pode resultar em punições.",
        discord.Color.gold()
    )
    await ctx.send(embed=embed)


# =========================
# .c - CATÁLOGO
# =========================

@bot.command(name="c")
@commands.guild_only()
async def catalogo(ctx):
    embed = embed_base(
        "🛒 CATÁLOGO ZYRON SENSI",
        "Confira os produtos e serviços disponíveis.\n\n"
        "📦 **Produtos:** consulte a equipe.\n"
        "💬 **Dúvidas ou compras:** abra um ticket com `.p`.\n\n"
        "Consulte a equipe para obter informações atualizadas."
    )
    await ctx.send(embed=embed)


# =========================
# .h - AJUDA
# =========================

@bot.command(name="h")
async def ajuda(ctx):
    embed = embed_base(
        "📚 COMANDOS | ZYRON SENSI",
        "**Comandos gerais**\n"
        "`.h` — mostra esta lista\n"
        "`.r` — exibe as regras\n"
        "`.c` — abre o catálogo\n"
        "`.v` — verifica a latência do bot\n"
        "`.s` — informações do servidor\n"
        "`.u` — informações do seu perfil\n"
        "`.p` — publica o painel de tickets (administradores)\n\n"
        "**Moderação**\n"
        "`.limpar 10` — apaga até 10 mensagens (administradores)\n"
        "`.fechar` — fecha o ticket atual, se você tiver autorização",
        discord.Color.blurple()
    )
    await ctx.send(embed=embed)


# =========================
# .v - LATÊNCIA
# =========================

@bot.command(name="v")
async def latencia(ctx):
    ms = round(bot.latency * 1000)
    embed = embed_base(
        "🏓 PONG!",
        f"Latência do bot: **{ms} ms**",
        discord.Color.green()
    )
    await ctx.send(embed=embed)


# =========================
# .s - SERVIDOR
# =========================

@bot.command(name="s")
@commands.guild_only()
async def servidor(ctx):
    guild = ctx.guild
    embed = embed_base(
        f"🏠 {guild.name}",
        f"**Membros:** {guild.member_count}\n"
        f"**Canais:** {len(guild.channels)}\n"
        f"**Cargos:** {len(guild.roles)}\n"
        f"**Criado em:** {guild.created_at.strftime('%d/%m/%Y')}"
    )

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    await ctx.send(embed=embed)


# =========================
# .u - PERFIL
# =========================

@bot.command(name="u")
@commands.guild_only()
async def usuario(ctx, membro: discord.Member = None):
    membro = membro or ctx.author

    embed = embed_base(
        f"👤 Perfil de {membro.display_name}",
        f"**Usuário:** {membro.mention}\n"
        f"**ID:** `{membro.id}`\n"
        f"**Conta criada:** {membro.created_at.strftime('%d/%m/%Y')}\n"
        f"**Entrou no servidor:** "
        f"{membro.joined_at.strftime('%d/%m/%Y') if membro.joined_at else 'Não disponível'}"
    )

    embed.set_thumbnail(url=membro.display_avatar.url)
    await ctx.send(embed=embed)


# =========================
# .limpar - MODERAÇÃO
# =========================

@bot.command(name="limpar")
@commands.guild_only()
@commands.has_permissions(manage_messages=True)
async def limpar(ctx, quantidade: int):
    if quantidade < 1 or quantidade > 100:
        await ctx.send("Escolha uma quantidade entre 1 e 100.")
        return

    apagadas = await ctx.channel.purge(
        limit=quantidade + 1
    )

    aviso = await ctx.send(
        f"🧹 {len(apagadas) - 1} mensagens apagadas."
    )

    import asyncio
    await asyncio.sleep(4)

    try:
        await aviso.delete()
    except discord.NotFound:
        pass


# =========================
# .fechar - FECHAR TICKET
# =========================

@bot.command(name="fechar")
@commands.guild_only()
async def fechar(ctx):
    canal = ctx.channel

    if not isinstance(canal, discord.TextChannel):
        return

    if not canal.name.startswith("ticket-"):
        await ctx.send("Este comando só pode ser usado em um canal de ticket.")
        return

    dono_id = None
    if canal.topic and "ID:" in canal.topic:
        try:
            dono_id = int(canal.topic.split("ID:")[-1].strip())
        except ValueError:
            dono_id = None

    cargo = ctx.guild.get_role(SUPPORT_ROLE_ID) if SUPPORT_ROLE_ID else None
    eh_suporte = cargo is not None and cargo in ctx.author.roles
    eh_admin = ctx.author.guild_permissions.manage_channels

    if ctx.author.id != dono_id and not eh_suporte and not eh_admin:
        await ctx.send("Você não tem permissão para fechar este ticket.")
        return

    await ctx.send("🔒 Fechando ticket em 5 segundos...")

    import asyncio
    await asyncio.sleep(5)

    try:
        await canal.delete(reason=f"Ticket fechado por {ctx.author}")
    except discord.Forbidden:
        await ctx.send("Não tenho permissão para excluir este canal.")


# =========================
# TRATAMENTO DE ERROS
# =========================

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Comando não encontrado. Use `.h` para ver os comandos.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("Você não tem permissão para usar esse comando.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("Falta um argumento. Consulte `.h`.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("Argumento inválido. Confira o comando e tente novamente.")
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send("Este comando só funciona dentro de um servidor.")
    else:
        print(f"Erro no comando: {error}")
        await ctx.send("Ocorreu um erro ao executar o comando.")


# =========================
# INICIAR BOT
# =========================

if not TOKEN:
    raise RuntimeError(
        "A variável de ambiente DISCORD_TOKEN não foi configurada."
    )

bot.run(TOKEN)

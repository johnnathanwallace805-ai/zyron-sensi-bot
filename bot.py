import os
import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID", "").strip()
SUPPORT_ROLE_ID = os.getenv("SUPPORT_ROLE_ID", "").strip()

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


def support_role(guild: discord.Guild):
    if SUPPORT_ROLE_ID.isdigit():
        return guild.get_role(int(SUPPORT_ROLE_ID))
    return None


class TicketPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Abrir ticket",
        style=discord.ButtonStyle.secondary,
        emoji="🎫",
        custom_id="zyron:open_ticket",
    )
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "Use este botão dentro do servidor.", ephemeral=True
            )
            return

        channel_name = f"ticket-{interaction.user.id}"
        existing = discord.utils.get(guild.text_channels, name=channel_name)
        if existing:
            await interaction.response.send_message(
                f"Você já tem um ticket aberto: {existing.mention}", ephemeral=True
            )
            return

        category = discord.utils.get(guild.categories, name="🎫・TICKETS")
        try:
            if category is None:
                category = await guild.create_category("🎫・TICKETS")

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True
                ),
            }
            bot_member = guild.me
            if bot_member:
                overwrites[bot_member] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True,
                    manage_channels=True
                )

            role = support_role(guild)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True, read_message_history=True
                )

            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"Ticket aberto por {interaction.user} ({interaction.user.id})",
            )
            await channel.send(
                f"{interaction.user.mention} seu ticket foi aberto!\n"
                "Explique aqui como podemos ajudar. A equipe responderá assim que possível.",
                view=CloseTicketView(),
            )
            await interaction.response.send_message(
                f"Ticket criado: {channel.mention}", ephemeral=True
            )
        except discord.Forbidden:
            message = (
                "Não consegui criar o ticket. Confira se o bot tem as permissões "
                "**Gerenciar canais**, **Ver canais** e **Enviar mensagens**."
            )
            if interaction.response.is_done():
                await interaction.followup.send(message, ephemeral=True)
            else:
                await interaction.response.send_message(message, ephemeral=True)


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Fechar ticket",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="zyron:close_ticket",
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        guild = interaction.guild
        if not isinstance(channel, discord.TextChannel) or guild is None:
            await interaction.response.send_message("Este botão só funciona em um ticket.", ephemeral=True)
            return

        is_owner = channel.name == f"ticket-{interaction.user.id}"
        role = support_role(guild)
        is_support = role is not None and role in interaction.user.roles
        has_manage_channels = interaction.user.guild_permissions.manage_channels
        if not (is_owner or is_support or has_manage_channels):
            await interaction.response.send_message(
                "Somente quem abriu o ticket ou a equipe pode fechá-lo.", ephemeral=True
            )
            return

        await interaction.response.send_message("Ticket será fechado em 3 segundos.")
        await discord.utils.sleep_until(discord.utils.utcnow() + __import__("datetime").timedelta(seconds=3))
        try:
            await channel.delete(reason=f"Ticket fechado por {interaction.user}")
        except discord.Forbidden:
            pass


@bot.event
async def setup_hook():
    bot.add_view(TicketPanel())
    bot.add_view(CloseTicketView())


@bot.event
async def on_ready():
    try:
        if GUILD_ID.isdigit():
            guild = discord.Object(id=int(GUILD_ID))
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
            print(f"Comandos sincronizados no servidor {GUILD_ID}.")
        else:
            await bot.tree.sync()
            print("Comandos globais sincronizados; podem demorar para aparecer.")
    except Exception as exc:
        print(f"Erro ao sincronizar comandos: {exc}")
    print(f"Conectado como {bot.user}.")


@bot.tree.command(name="painel", description="Publica o painel de suporte da ZYRON SENSI.")
@app_commands.checks.has_permissions(manage_channels=True)
async def painel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🐺 ZYRON SENSI • SUPORTE",
        description=(
            "Precisa de ajuda com seu pedido ou com os packs de sensibilidade?\n\n"
            "Clique em **Abrir ticket** para criar um canal privado com a equipe."
        ),
        color=discord.Color.from_rgb(225, 225, 225),
    )
    embed.set_footer(text="ZYRON SENSI • Atendimento")
    await interaction.response.send_message(embed=embed, view=TicketPanel())


@bot.tree.command(name="regras", description="Publica as regras básicas da ZYRON SENSI.")
@app_commands.checks.has_permissions(manage_guild=True)
async def regras(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📜 REGRAS • ZYRON SENSI",
        description=(
            "1. Respeite todos os membros.\n"
            "2. Não faça spam nem divulgue links sem autorização.\n"
            "3. Confira as informações dos packs antes de comprar.\n"
            "4. Use os canais corretos para dúvidas e suporte.\n"
            "5. Não compartilhe dados pessoais ou informações de pagamento no chat público."
        ),
        color=discord.Color.from_rgb(225, 225, 225),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="catalogo", description="Publica o catálogo demonstrativo de packs.")
@app_commands.checks.has_permissions(manage_guild=True)
async def catalogo(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚙️ CATÁLOGO • ZYRON SENSI",
        description=(
            "**START** — R$ 4,90\nPack básico de sensibilidade.\n\n"
            "**PRO** — R$ 9,90\nPack intermediário de sensibilidade.\n\n"
            "**ELITE** — R$ 14,90\nPack avançado de sensibilidade.\n\n"
            "*Preços demonstrativos: edite antes de divulgar. "
            "Este protótipo não entrega packs nem processa pagamentos automaticamente.*"
        ),
        color=discord.Color.from_rgb(225, 225, 225),
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    if isinstance(error, app_commands.MissingPermissions):
        message = "Você precisa ter a permissão necessária para usar este comando."
    else:
        message = "Não foi possível executar esse comando. Tente novamente ou confira os logs do bot."
        print(f"Erro no comando: {error}")
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.HTTPException:
        pass


if not TOKEN:
    raise RuntimeError("Defina DISCORD_TOKEN nas variáveis de ambiente da hospedagem.")

bot.run(TOKEN)

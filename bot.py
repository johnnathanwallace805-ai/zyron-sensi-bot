
import os
import asyncio
import logging
import traceback
from datetime import datetime, timezone

import discord
from discord.ext import commands

# =====================================================
# CONFIGURAÇÕES
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("zyron_sensi")

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0") or "0")
SUPPORT_ROLE_ID = int(os.getenv("SUPPORT_ROLE_ID", "0") or "0")
TICKET_CATEGORY_ID = int(os.getenv("TICKET_CATEGORY_ID", "0") or "0")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix=".",
    intents=intents,
    help_command=None,
)

_views_registradas = False


# =====================================================
# EMBEDS E FUNÇÕES AUXILIARES
# =====================================================

def embed_base(titulo, descricao, cor=discord.Color.blurple()):
    return discord.Embed(
        title=titulo,
        description=descricao,
        color=cor,
        timestamp=datetime.now(timezone.utc),
    )


def extrair_dono_ticket(canal):
    if not canal.topic or "ID:" not in canal.topic:
        return None

    try:
        return int(canal.topic.rsplit("ID:", 1)[1].strip())
    except (ValueError, TypeError):
        return None


def pode_fechar_ticket(membro, guild, dono_id):
    cargo = (
        guild.get_role(SUPPORT_ROLE_ID)
        if SUPPORT_ROLE_ID
        else None
    )

    eh_dono = membro.id == dono_id

    eh_suporte = (
        cargo is not None
        and isinstance(membro, discord.Member)
        and cargo in membro.roles
    )

    permissoes = getattr(membro, "guild_permissions", None)

    eh_admin = permissoes is not None and (
        permissoes.manage_channels
        or permissoes.administrator
    )

    return eh_dono or eh_suporte or eh_admin


async def responder_interacao(interaction, mensagem):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(
                mensagem,
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                mensagem,
                ephemeral=True,
            )
    except discord.HTTPException:
        logger.exception(
            "Não foi possível responder à interação."
        )


# =====================================================
# BOTÃO PARA FECHAR TICKETS
# =====================================================

class FecharTicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Fechar ticket",
        emoji="🔒",
        style=discord.ButtonStyle.red,
        custom_id="zyron:fechar_ticket",
    )
    async def fechar_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        canal = interaction.channel
        guild = interaction.guild

        if not isinstance(canal, discord.TextChannel) or guild is None:
            await responder_interacao(
                interaction,
                "Não foi possível fechar este ticket.",
            )
            return

        if not canal.name.startswith("ticket-"):
            await responder_interacao(
                interaction,
                "Este botão só pode ser usado em um ticket.",
            )
            return

        dono_id = extrair_dono_ticket(canal)

        if not pode_fechar_ticket(
            interaction.user,
            guild,
            dono_id,
        ):
            await responder_interacao(
                interaction,
                "Somente o dono do ticket, a equipe de suporte "
                "ou um administrador pode fechá-lo.",
            )
            return

        await interaction.response.send_message(
            "🔒 Ticket será fechado em 5 segundos."
        )

        await asyncio.sleep(5)

        try:
            await canal.delete(
                reason=f"Ticket fechado por {interaction.user}",
            )
        except discord.Forbidden:
            logger.exception(
                "Sem permissão para excluir o ticket."
            )
        except discord.HTTPException:
            logger.exception(
                "Falha ao excluir o ticket."
            )


# =====================================================
# BOTÃO PARA ABRIR TICKETS
# =====================================================

class TicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Abrir ticket",
        emoji="🎫",
        style=discord.ButtonStyle.green,
        custom_id="zyron:abrir_ticket",
    )
    async def abrir_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        guild = interaction.guild

        if guild is None:
            await responder_interacao(
                interaction,
                "Este botão só funciona dentro de um servidor.",
            )
            return

        nome_canal = f"ticket-{interaction.user.id}"

        existente = discord.utils.get(
            guild.text_channels,
            name=nome_canal,
        )

        if existente:
            await responder_interacao(
                interaction,
                f"Você já tem um ticket aberto: {existente.mention}",
            )
            return

        categoria = (
            guild.get_channel(TICKET_CATEGORY_ID)
            if TICKET_CATEGORY_ID
            else None
        )

        if not isinstance(categoria, discord.CategoryChannel):
            categoria = None

        cargo_suporte = (
            guild.get_role(SUPPORT_ROLE_ID)
            if SUPPORT_ROLE_ID
            else None
        )

        bot_member = guild.me

        if bot_member is None and bot.user is not None:
            try:
                bot_member = await guild.fetch_member(bot.user.id)
            except discord.HTTPException:
                await responder_interacao(
                    interaction,
                    "Não consegui verificar minhas permissões no servidor.",
                )
                return

        if bot_member is None:
            await responder_interacao(
                interaction,
                "Não consegui identificar o bot neste servidor.",
            )
            return

        permissoes = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False,
            ),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
            ),
            bot_member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True,
            ),
        }

        if cargo_suporte is not None:
            permissoes[cargo_suporte] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
            )

        await interaction.response.defer(
            ephemeral=True,
            thinking=True,
        )

        try:
            canal = await guild.create_text_channel(
                name=nome_canal,
                category=categoria,
                overwrites=permissoes,
                topic=(
                    f"Ticket de {interaction.user} "
                    f"| ID: {interaction.user.id}"
                ),
                reason=f"Ticket aberto por {interaction.user}",
            )

            await canal.send(
                f"Olá {interaction.user.mention}! 👋\n"
                "Explique seu problema e aguarde a equipe de suporte.",
                view=FecharTicketView(),
            )

            await interaction.followup.send(
                f"Ticket criado: {canal.mention}",
                ephemeral=True,
            )

        except discord.Forbidden:
            logger.exception(
                "Permissões insuficientes ao criar ticket."
            )
            await interaction.followup.send(
                "Não tenho permissão para criar tickets. "
                "Verifique se tenho Gerenciar Canais, "
                "Ver Canais e Enviar Mensagens.",
                ephemeral=True,
            )

        except discord.HTTPException:
            logger.exception(
                "Erro da API do Discord ao criar ticket."
            )
            await interaction.followup.send(
                "O Discord não conseguiu criar o ticket. "
                "Tente novamente.",
                ephemeral=True,
            )

        except Exception:
            logger.exception(
                "Erro inesperado ao abrir ticket."
            )
            await interaction.followup.send(
                "Ocorreu um erro ao abrir o ticket. "
                "Consulte o console da aplicação.",
                ephemeral=True,
            )


# =====================================================
# EVENTOS DO BOT
# =====================================================

@bot.event
async def on_ready():
    global _views_registradas

    if not _views_registradas:
        bot.add_view(TicketView())
        bot.add_view(FecharTicketView())
        _views_registradas = True

    logger.info(
        "ZYRON SENSI conectado como %s (ID: %s)",
        bot.user,
        bot.user.id,
    )
    logger.info("Prefixo dos comandos: .")


@bot.event
async def on_disconnect():
    logger.warning(
        "Conexão com o Gateway do Discord encerrada."
    )


@bot.event
async def on_resumed():
    logger.info(
        "Sessão do Gateway do Discord retomada."
    )


# =====================================================
# .p - PAINEL DE TICKETS
# =====================================================

@bot.command(name="p")
@commands.guild_only()
@commands.has_guild_permissions(manage_guild=True)
async def painel(ctx):
    embed = embed_base(
        "🎫 ZYRON SENSI | SUPORTE",
        "Precisa de ajuda? Clique no botão abaixo para abrir um ticket.\n\n"
        "• Atendimento individual\n"
        "• Suporte da equipe\n"
        "• Um ticket por usuário",
    )

    await ctx.send(
        embed=embed,
        view=TicketView(),
    )


# =====================================================
# .r - REGRAS
# =====================================================

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
        discord.Color.gold(),
    )

    await ctx.send(embed=embed)


# =====================================================
# .c - CATÁLOGO
# =====================================================

@bot.command(name="c")
@commands.guild_only()
async def catalogo(ctx):
    embed = embed_base(
        "🛒 CATÁLOGO ZYRON SENSI",
        "Confira os produtos e serviços disponíveis.\n\n"
        "📦 **Produtos:** consulte a equipe.\n"
        "💬 **Dúvidas ou compras:** abra um ticket com `.p`.\n\n"
        "Consulte a equipe para obter informações atualizadas.",
    )

    await ctx.send(embed=embed)


# =====================================================
# .h - AJUDA
# =====================================================

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
        discord.Color.blurple(),
    )

    await ctx.send(embed=embed)


# =====================================================
# .v - LATÊNCIA
# =====================================================

@bot.command(name="v")
async def latencia(ctx):
    ms = round(bot.latency * 1000)

    embed = embed_base(
        "🏓 PONG!",
        f"Latência do bot: **{ms} ms**",
        discord.Color.green(),
    )

    await ctx.send(embed=embed)


# =====================================================
# .s - INFORMAÇÕES DO SERVIDOR
# =====================================================

@bot.command(name="s")
@commands.guild_only()
async def servidor(ctx):
    guild = ctx.guild

    membros = (
        guild.member_count
        if guild.member_count is not None
        else "Não disponível"
    )

    embed = embed_base(
        f"🏠 {guild.name}",
        f"**Membros:** {membros}\n"
        f"**Canais:** {len(guild.channels)}\n"
        f"**Cargos:** {len(guild.roles)}\n"
        f"**Criado em:** {guild.created_at.strftime('%d/%m/%Y')}",
    )

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    await ctx.send(embed=embed)


# =====================================================
# .u - PERFIL
# =====================================================

@bot.command(name="u")
@commands.guild_only()
async def usuario(ctx, membro: discord.Member = None):
    membro = membro or ctx.author

    entrada = (
        membro.joined_at.strftime("%d/%m/%Y")
        if membro.joined_at
        else "Não disponível"
    )

    embed = embed_base(
        f"👤 Perfil de {membro.display_name}",
        f"**Usuário:** {membro.mention}\n"
        f"**ID:** `{membro.id}`\n"
        f"**Conta criada:** {membro.created_at.strftime('%d/%m/%Y')}\n"
        f"**Entrou no servidor:** {entrada}",
    )

    embed.set_thumbnail(
        url=membro.display_avatar.url
    )

    await ctx.send(embed=embed)


# =====================================================
# .limpar - MODERAÇÃO
# =====================================================

@bot.command(name="limpar")
@commands.guild_only()
@commands.has_guild_permissions(manage_messages=True)
async def limpar(ctx, quantidade: int):
    if quantidade < 1 or quantidade > 100:
        await ctx.send(
            "Escolha uma quantidade entre 1 e 100."
        )
        return

    try:
        apagadas = await ctx.channel.purge(
            limit=quantidade + 1,
        )

        total = max(0, len(apagadas) - 1)

        aviso = await ctx.send(
            f"🧹 {total} mensagens apagadas."
        )

        await asyncio.sleep(4)

        try:
            await aviso.delete()
        except discord.NotFound:
            pass

    except discord.Forbidden:
        await ctx.send(
            "Não tenho permissão para gerenciar mensagens neste canal."
        )

    except discord.HTTPException:
        logger.exception(
            "Falha ao limpar mensagens."
        )
        await ctx.send(
            "O Discord não conseguiu apagar as mensagens. Tente novamente."
        )


# =====================================================
# .fechar - FECHAR TICKET
# =====================================================

@bot.command(name="fechar")
@commands.guild_only()
async def fechar(ctx):
    canal = ctx.channel

    if (
        not isinstance(canal, discord.TextChannel)
        or not canal.name.startswith("ticket-")
    ):
        await ctx.send(
            "Este comando só pode ser usado em um canal de ticket."
        )
        return

    dono_id = extrair_dono_ticket(canal)

    if not pode_fechar_ticket(
        ctx.author,
        ctx.guild,
        dono_id,
    ):
        await ctx.send(
            "Você não tem permissão para fechar este ticket."
        )
        return

    await ctx.send(
        "🔒 Fechando ticket em 5 segundos..."
    )

    await asyncio.sleep(5)

    try:
        await canal.delete(
            reason=f"Ticket fechado por {ctx.author}",
        )

    except discord.Forbidden:
        await ctx.send(
            "Não tenho permissão para excluir este canal."
        )

    except discord.HTTPException:
        logger.exception(
            "Falha ao excluir ticket pelo comando .fechar."
        )
        await ctx.send(
            "O Discord não conseguiu excluir o ticket. Tente novamente."
        )


# =====================================================
# TRATAMENTO GLOBAL DE ERROS
# =====================================================

@bot.event
async def on_command_error(ctx, error):
    erro = getattr(error, "original", error)

    if isinstance(erro, commands.CommandNotFound):
        await ctx.send(
            "Comando não encontrado. Use `.h` para ver os comandos."
        )

    elif isinstance(erro, commands.MissingPermissions):
        await ctx.send(
            "Você não tem permissão para usar esse comando."
        )

    elif isinstance(erro, commands.BotMissingPermissions):
        await ctx.send(
            "Não tenho as permissões necessárias para executar esse comando."
        )

    elif isinstance(erro, commands.MissingRequiredArgument):
        await ctx.send(
            "Falta um argumento. Consulte `.h`."
        )

    elif isinstance(erro, commands.BadArgument):
        await ctx.send(
            "Argumento inválido. Confira o comando e tente novamente."
        )

    elif isinstance(erro, commands.NoPrivateMessage):
        await ctx.send(
            "Este comando só funciona dentro de um servidor."
        )

    elif isinstance(erro, commands.CommandOnCooldown):
        await ctx.send(
            f"Aguarde {erro.retry_after:.1f} segundos antes de tentar novamente."
        )

    elif isinstance(erro, commands.CheckFailure):
        await ctx.send(
            "Você não atende aos requisitos para usar esse comando."
        )

    else:
        logger.error(
            "Erro no comando %s:\n%s",
            getattr(ctx.command, "qualified_name", "desconhecido"),
            "".join(
                traceback.format_exception(
                    type(erro),
                    erro,
                    erro.__traceback__,
                )
            ),
        )

        try:
            await ctx.send(
                "Ocorreu um erro ao executar o comando. "
                "O erro completo foi registrado no console."
            )
        except discord.HTTPException:
            logger.exception(
                "Não foi possível enviar a mensagem de erro."
            )


# =====================================================
# INICIALIZAÇÃO
# =====================================================

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError(
            "A variável DISCORD_TOKEN não foi configurada na Square Cloud."
        )

    logger.info("Iniciando ZYRON SENSI...")

    bot.run(
        TOKEN,
        log_handler=None,
    )

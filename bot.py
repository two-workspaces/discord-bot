"""Discord bot starter for Railway: discord.py, slash commands, no privileged intents.

It answers slash commands, direct messages and @mentions. Without AI settings it
echoes what you send. Set OPENAI_API_KEY (and OPENAI_BASE_URL for OpenRouter, Groq,
DeepSeek or any other OpenAI-compatible API) and it chats with the model instead.
Add your own slash commands in register().
"""
import asyncio
import logging
import os
import signal
import time
from collections import defaultdict, deque

import aiohttp
import discord
from discord import app_commands

logging.basicConfig(format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("bot")
# discord.py warns twice at start that voice libraries are missing; this bot has no voice.
logging.getLogger("discord.client").addFilter(lambda record: "voice will NOT be supported" not in record.getMessage())


def clean_token(raw: str) -> str:
    """The token as Discord wants it: no quotes, spaces or pasted 'Bot ' prefix."""
    token = raw.strip().strip("\"'").strip()
    return token[4:].strip() if token.lower().startswith("bot ") else token


TOKEN = clean_token(os.getenv("DISCORD_TOKEN") or os.getenv("DISCORD_BOT_TOKEN") or "")
AI_KEY = os.getenv("OPENAI_API_KEY", "").strip()
AI_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
AI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "You are a helpful assistant in a Discord server. Keep answers short.")
LIMIT = 2000  # Discord's message length limit


def parse_ids(raw: str) -> tuple[set[int], list[str]]:
    """Numeric IDs, plus whatever else was typed (a username, a typo)."""
    ids, bad = set(), []
    for part in raw.replace(",", " ").replace(";", " ").split():
        try:
            ids.add(int(part))
        except ValueError:
            bad.append(part)
    return ids, bad


# User IDs and server IDs share one list: Discord IDs are unique across both.
ALLOWED, BAD_IDS = parse_ids(os.getenv("ALLOWED_IDS", ""))
# An allowlist that held only bad entries locks the bot instead of opening it to everyone.
LOCKED = bool(BAD_IDS) and not ALLOWED

# Last 20 messages per channel, in memory: lost on redeploy, which suits a starter.
history: dict[int, deque] = defaultdict(lambda: deque(maxlen=20))


def allowed(user: discord.abc.User, guild: discord.Guild | None) -> bool:
    if LOCKED:
        return False
    return not ALLOWED or user.id in ALLOWED or (guild is not None and guild.id in ALLOWED)


def not_allowed(user: discord.abc.User) -> str:
    return f"Not allowed. Ask the bot's owner to add your ID ({user.id}) or this server's ID to ALLOWED_IDS."


def id_text(user: discord.abc.User, guild: discord.Guild | None) -> str:
    return f"Your Discord user ID: {user.id}" + (f"\nThis server's ID: {guild.id}" if guild else "")


async def ask_ai(channel_id: int, text: str) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history[channel_id], {"role": "user", "content": text}]
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        async with session.post(f"{AI_URL}/chat/completions", headers={"Authorization": f"Bearer {AI_KEY}"},
                                json={"model": AI_MODEL, "messages": messages}) as r:
            if r.status >= 400:
                raise RuntimeError(f"HTTP {r.status}: {(await r.text())[:300]}")
            answer = (await r.json())["choices"][0]["message"]["content"] or "(the model returned no text)"
    history[channel_id] += [{"role": "user", "content": text}, {"role": "assistant", "content": answer}]
    return answer


async def answer_for(channel_id: int, text: str) -> str:
    if not AI_KEY:
        return text
    try:
        return await ask_ai(channel_id, text)
    except Exception as e:  # show the provider's error instead of going silent
        log.warning("AI request failed: %s", e)
        return f"AI request failed: {e}"


def chunks(text: str) -> list[str]:
    return [text[i:i + LIMIT] for i in range(0, len(text), LIMIT)] or ["(empty)"]


class Panel(discord.ui.View):
    """Buttons under /hello. No timeout and fixed custom_ids, so they still work after a redeploy."""

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="My Discord ID", style=discord.ButtonStyle.secondary, custom_id="starter:id")
    async def show_id(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message(id_text(interaction.user, interaction.guild), ephemeral=True)

    @discord.ui.button(label="Reset chat", style=discord.ButtonStyle.secondary, custom_id="starter:reset")
    async def reset(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        history.pop(interaction.channel_id, None)
        await interaction.response.send_message("Chat history cleared for this channel.", ephemeral=True)


def register(tree: app_commands.CommandTree) -> None:
    """The slash commands. Add yours here; they're sent to Discord on every start."""

    @tree.command(description="Say hello and show what this bot does")
    async def hello(interaction: discord.Interaction) -> None:
        mode = (f"I answer with {AI_MODEL}." if AI_KEY
                else "I echo what you send. Add OPENAI_API_KEY to make me an AI chat bot.")
        await interaction.response.send_message(
            f"Hi {interaction.user.display_name}! {mode}\nUse /ask, mention me in a channel, or send me a direct message.",
            view=Panel())

    @tree.command(description="Ask the bot something")
    @app_commands.describe(question="What you want to ask")
    async def ask(interaction: discord.Interaction, question: str) -> None:
        if not allowed(interaction.user, interaction.guild):
            await interaction.response.send_message(not_allowed(interaction.user), ephemeral=True)
            return
        await interaction.response.defer()  # an AI answer can take longer than Discord's 3 seconds
        for part in chunks(await answer_for(interaction.channel_id, question)):
            await interaction.followup.send(part)

    @tree.command(name="id", description="Show your Discord user ID and this server's ID")
    async def show_id(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(id_text(interaction.user, interaction.guild), ephemeral=True)

    @tree.command(description="Forget the conversation in this channel")
    async def reset(interaction: discord.Interaction) -> None:
        history.pop(interaction.channel_id, None)
        await interaction.response.send_message("Chat history cleared for this channel.", ephemeral=True)

    @tree.command(description="Check that the bot is alive")
    async def ping(interaction: discord.Interaction) -> None:
        await interaction.response.send_message(f"Pong! {round(interaction.client.latency * 1000)} ms", ephemeral=True)

    @tree.error
    async def on_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        log.error("/%s failed", interaction.command.name if interaction.command else "?", exc_info=error)
        text = "Something went wrong. The bot's logs have the details."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(text, ephemeral=True)
            else:
                await interaction.response.send_message(text, ephemeral=True)
        except discord.HTTPException:
            pass


class Bot(discord.Client):
    def __init__(self) -> None:
        # Default intents: no toggles needed in the Developer Portal. Discord still delivers the
        # text of direct messages and of messages that mention the bot. AllowedMentions.none()
        # keeps an echoed or AI-written "@everyone" from pinging anyone.
        super().__init__(intents=discord.Intents.default(), allowed_mentions=discord.AllowedMentions.none())
        self.tree = app_commands.CommandTree(self)
        self.announced = False

    async def setup_hook(self) -> None:
        self.add_view(Panel())
        register(self.tree)
        try:
            synced = await self.tree.sync()
            log.info("Registered %d slash commands: %s", len(synced), ", ".join(f"/{c.name}" for c in synced))
        except discord.HTTPException as e:  # the bot still answers mentions and direct messages
            log.error("Couldn't register slash commands (%s). They are sent again on the next start.", e)

    async def on_ready(self) -> None:
        if self.announced:  # on_ready fires again after every reconnect
            return
        self.announced = True
        permissions = discord.Permissions(view_channel=True, send_messages=True, send_messages_in_threads=True,
                                          read_message_history=True)
        log.info("Logged in as %s, in %d server(s). Invite link: %s", self.user, len(self.guilds),
                 discord.utils.oauth_url(self.application_id, permissions=permissions,
                                         scopes=("bot", "applications.commands")))

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if message.guild is not None and self.user not in message.mentions:
            return  # in a server, only messages that mention the bot
        text = message.content.replace(f"<@{self.user.id}>", "").replace(f"<@!{self.user.id}>", "").strip()
        try:
            if not allowed(message.author, message.guild):
                await message.reply(not_allowed(message.author))
            elif not text:
                await message.reply("Write something after the mention, or try /hello.")
            else:
                async with message.channel.typing():
                    answer = await answer_for(message.channel.id, text)
                for part in chunks(answer):
                    await message.reply(part)
        except discord.Forbidden:
            log.warning("No permission to answer in #%s (%s). Give the bot Send Messages there.",
                        message.channel, message.guild)


def idle(reason: str) -> None:
    # A bot that exits on a bad token crash-loops and shows as a failed deploy.
    # Stay up with a clear log line; the fix is a variable change and a redeploy.
    log.error("%s Set DISCORD_TOKEN (Developer Portal > your app > Bot > Reset Token) in the Variables tab; "
              "Railway redeploys.", reason)
    while True:
        time.sleep(3600)


def stop(*_: object) -> None:
    raise KeyboardInterrupt  # lets discord.py close the connection, so the bot goes offline at once


def main() -> None:
    signal.signal(signal.SIGTERM, stop)
    if BAD_IDS:
        log.error("ALLOWED_IDS takes numeric IDs; ignoring %s. Run /id for yours.%s",
                  ", ".join(BAD_IDS), " Nobody can chat until it holds one." if LOCKED else "")
    if not TOKEN:
        idle("DISCORD_TOKEN is empty.")
    log.info("Starting (%s, %s)", f"AI: {AI_MODEL}" if AI_KEY else "echo mode",
             "locked" if LOCKED else f"{len(ALLOWED)} allowed IDs" if ALLOWED else "open to everyone")
    delay = 5
    while True:
        try:
            # A new client per attempt: one that failed to log in can't be started again.
            Bot().run(TOKEN, log_handler=None)
            return
        except discord.LoginFailure:
            idle("Discord rejected DISCORD_TOKEN.")
        except discord.PrivilegedIntentsRequired:
            idle("The code asks for a privileged intent that is off in the Developer Portal (Bot > Privileged "
                 "Gateway Intents). Turn it on there, or remove it from the code.")
        except (aiohttp.ClientError, discord.DiscordException, OSError, asyncio.TimeoutError) as e:
            # Discord unreachable or erroring at startup: wait it out instead of crash-looping
            log.warning("Can't reach Discord (%s); retrying in %d s.", e or type(e).__name__, delay)
            time.sleep(delay)
            delay = min(delay * 2, 300)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:  # SIGTERM while idling or between retries
        pass

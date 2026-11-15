# Deploy and Host a Discord Bot (Python) on Railway

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/discord?referralCode=sLjDXb&utm_medium=integration&utm_source=button&utm_campaign=discord)

A Python Discord bot that is running a minute after you paste its token: slash commands, buttons, answers to mentions and direct messages, an allowlist, and optional AI chat through any OpenAI-compatible API (OpenAI, OpenRouter, Groq, DeepSeek, a self-hosted model). It's one short file built on [discord.py](https://discordpy.readthedocs.io), meant to be ejected and made your own.

## About Hosting a Discord Bot

The bot keeps one outgoing connection to Discord's gateway, so it needs no public domain, webhook or certificate. One small service, no database.

- It uses no privileged intents, so there is nothing to switch on in the Developer Portal. Discord still gives a bot the text of direct messages and of messages that mention it, and slash commands need no intent at all.
- Without an AI key it echoes what you send, so you can see it working first.
- With `OPENAI_API_KEY` set it chats with the model, keeping the last 20 messages of each channel as context.
- A missing or wrong token, a name in the allowlist or Discord being unreachable at start doesn't crash-loop the service: the bot waits or retries and says in its logs what to fix.

## Common Use Cases

- An AI assistant for your server, on any model you choose
- A starting point for a moderation, notification or community bot
- A private bot for one server or a few people, locked to listed IDs
- Learning bot development with a working deploy from minute one

## Dependencies for Discord Bot Hosting

- A bot token from the [Discord Developer Portal](https://discord.com/developers/applications): *New Application*, open *Bot*, press *Reset Token* and copy it.
- Optional: an API key for an OpenAI-compatible provider.

### Deployment Dependencies

- [discord.py docs](https://discordpy.readthedocs.io)
- [Discord developer docs](https://discord.com/developers/docs/intro)
- [OpenRouter](https://openrouter.ai) for one key to many models (optional)

### Implementation Details

**First use:**

1. Paste the token as `DISCORD_TOKEN` and deploy.
2. Open the service's *Deploy Logs*. The line that starts with `Logged in as` ends with an invite link. Open it and add the bot to your server.
3. In the server, type `/hello`.

If the slash commands don't show up right after the invite, reload Discord (Ctrl+R): the app caches the command list.

**Commands:** `/hello` (welcome and buttons), `/ask` (ask a question), `/id` (your user ID and the server's ID), `/reset` (clears the AI's memory of this channel) and `/ping`. You can also mention the bot in a channel or send it a direct message.

**AI chat:** set `OPENAI_API_KEY`, then `OPENAI_BASE_URL` and `OPENAI_MODEL` for your provider:

| Provider | `OPENAI_BASE_URL` | `OPENAI_MODEL` example |
| --- | --- | --- |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` |
| OpenRouter | `https://openrouter.ai/api/v1` | `anthropic/claude-sonnet-4.5` |
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| DeepSeek | `https://api.deepseek.com` | `deepseek-chat` |

Change the bot's personality with `SYSTEM_PROMPT`.

**Lock it down:** everyone in a server with the bot can use it, and your AI key pays for it. Run `/id`, then put your server's ID or your own user ID (comma-separated for several) in `ALLOWED_IDS`. A server ID lets everyone in that server chat; a user ID lets that person chat anywhere, direct messages included. An entry that isn't a number is ignored, and if none are numbers the bot answers nobody until you fix it. Also turn off *Public Bot* on the Developer Portal's *Bot* page, so only you can add the bot to a server.

**Make it yours:** eject the template in the service's settings to get your own copy of the repo. Add slash commands in `register()` in `bot.py`; every push redeploys and sends the new command list to Discord.

Notes and limits:

- In a server the bot only reads messages that mention it. To read every message, turn on *Message Content Intent* in the Developer Portal and set `intents.message_content = True` in the code. If the code asks for an intent that's off in the Portal, the bot stays up and says so in its logs.
- Chat memory is kept in RAM and is cleared on each redeploy.
- Answers longer than Discord's 2,000-character limit are sent as several messages.
- The bot never pings `@everyone`, roles or users, whatever the AI writes.
- No voice support: the voice libraries aren't installed.

Discord is a trademark of Discord Inc. This community template is not affiliated with or endorsed by Discord.

## Why Deploy a Discord Bot on Railway?

Railway is a singular platform to deploy your infrastructure stack. Railway will host your infrastructure so you don't have to deal with configuration, while allowing you to vertically and horizontally scale it.

By deploying a Discord bot on Railway, you are one step closer to supporting a complete full-stack application with minimal burden. Host your servers, databases, AI agents, and more on Railway.

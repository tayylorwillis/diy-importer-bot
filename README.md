# Discord History Importer

Replays a [DiscordChatExporter](https://github.com/Tyrrrz/DiscordChatExporter) HTML
export back into a live Discord channel, one message at a time, using a
webhook so each message shows up with the **original author's name and
avatar**.

It handles:
- Message text, links, and quoted replies (shown as a `> replying to ...` line)
- Image/video/file attachments
- Rich link embeds (YouTube, Tenor gifs, etc.) — rebuilt as native Discord embeds
- Reactions (re-applied after each message is sent, unicode emoji only —
  custom emoji from the old server usually won't exist in the new one)
- Resuming: progress is saved after every message, so if the bot is
  stopped or crashes, re-running the same command picks up where it left off

## 1. Install dependencies

```bash
pip install -r requirements.txt
```

## 2. Create a Discord bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications) → **New Application**.
2. Go to the **Bot** tab → **Add Bot**.
3. Under **Privileged Gateway Intents**, enable **Message Content Intent**.
4. Copy the bot **Token**.
5. Go to **OAuth2 → URL Generator**, check the `bot` scope, and under
   **Bot Permissions** check: `Manage Webhooks`, `Send Messages`,
   `Embed Links`, `Add Reactions`, `Read Message History`.
6. Open the generated URL and invite the bot to your server.

## 3. Configure

```bash
cp .env.example .env
```

Fill in:
- `DISCORD_BOT_TOKEN` — the token from step 2
- `TARGET_CHANNEL_ID` — right-click the destination channel in Discord
  (enable Developer Mode in Settings → Advanced first) → **Copy Channel ID**

## 4. Parse the HTML export

```bash
python parse_export.py "{html file name}" messages.jsonl
```

This produces `messages.jsonl`, one JSON object per line, in chronological order.

## 5. Run the import

```bash
python bot.py messages.jsonl
```

The bot logs in, posts each message with a short delay between sends
(`DELAY_SECONDS` in `.env`, default 1.5s — large exports can take hours;
that's expected and safe), and exits automatically when done.

To stop early, just Ctrl+C — a `messages.jsonl.progress` file tracks which
message IDs have already been sent, so re-running `python bot.py
messages.jsonl` continues instead of duplicating messages.

## Notes & limitations

- Discord's rate limits mean large channel histories (thousands of
  messages) will take a long time to fully replay — this is expected.
- Original send *timestamps* can't be spoofed; messages will show up
  posted "now" in the new channel, in the correct relative order.
- Custom server emoji/reactions from the original server won't carry
  over unless an emoji with the same name exists in the destination server.
- The webhook is created automatically.
- Cannot search for messages by user (from: {user}).

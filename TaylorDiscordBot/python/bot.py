import asyncio
import json
import os
import sys

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = os.getenv("TARGET_CHANNEL_ID")
DELAY_SECONDS = 0.3 # i dont think this does anything
WEBHOOK_NAME = "original general importer"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


def load_messages(path):
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_progress(progress_path):
    if os.path.exists(progress_path):
        with open(progress_path, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_progress(progress_path, done_ids):
    with open(progress_path, "w", encoding="utf-8") as f:
        json.dump(list(done_ids), f)

# wtf is a webhook
async def get_or_create_webhook(channel):
    webhooks = await channel.webhooks()
    for wh in webhooks:
        if wh.name == WEBHOOK_NAME:
            return wh
    return await channel.create_webhook(name=WEBHOOK_NAME)


def build_embeds(msg):
    embeds = []

    for e in msg.get("embeds", []):
        has_content = any(e.get(k) for k in ("title", "description", "author", "thumbnail", "image", "footer"))
        if not has_content:
            continue

        embed = discord.Embed(
            title=e.get("title"),
            description=e.get("description"),
            url=e.get("url") if e.get("title") else None,  # url needs a title to be clickable
            color=e.get("color", 0x2F3136),
        )
        if e.get("author"):
            embed.set_author(name=e["author"])
        if e.get("thumbnail"):
            embed.set_thumbnail(url=e["thumbnail"])
        if e.get("image"):
            embed.set_image(url=e["image"])
        if e.get("footer"):
            embed.set_footer(text=e["footer"])
        embeds.append(embed)
        if len(embeds) >= 10:
            break

    return embeds


def build_content(msg):
    parts = []
    if msg.get("reply"):
        reply = msg["reply"]
        snippet = (reply.get("content") or "").strip()
        if len(snippet) > 80:
            snippet = snippet[:80] + "…"
        parts.append(f"> replying to **{reply.get('author') or 'someone'}**: {snippet}")
    if msg.get("content"):
        parts.append(msg["content"])
    for url in msg.get("attachments", []):
        parts.append(url)
    for e in msg.get("embeds", []):
        if e.get("video"):
            parts.append(e["video"])
    content = "\n".join(p for p in parts if p)
    return content[:2000] if content else None


def build_display_name(msg):
    author = msg.get("author") or "Unknown"
    username = msg.get("author_username")
    name = author if not username or username == author else f"{author} ({username})"
    return name[:80]


async def send_message(webhook, msg):
    content = build_content(msg)
    embeds = build_embeds(msg)

    if not content and not embeds:
        return None

    sent = await webhook.send(
        content=content,
        username=build_display_name(msg),
        avatar_url=msg.get("avatar_url") or discord.utils.MISSING,
        embeds=embeds,
        wait=True,
    )
    return sent


async def apply_reactions(channel, sent_message, reactions):
    for r in reactions:
        emoji = r.get("emoji")
        if not emoji:
            continue
        try:
            await sent_message.add_reaction(emoji)
        except discord.HTTPException:
            # idk if emojis will exist still
            pass


async def run_import(jsonl_path):
    await bot.wait_until_ready()

    channel = bot.get_channel(int(CHANNEL_ID))
    if channel is None:
        channel = await bot.fetch_channel(int(CHANNEL_ID))

    messages = load_messages(jsonl_path)
    progress_path = jsonl_path + ".progress"
    done_ids = load_progress(progress_path)

    webhook = await get_or_create_webhook(channel)

    total = len(messages)
    remaining = [m for m in messages if m["id"] not in done_ids]
    print(f"{len(done_ids)}/{total} already imported. {len(remaining)} to go.")

    for i, msg in enumerate(remaining, start=1):
        success = True
        try:
            sent = await send_message(webhook, msg)
            if sent is not None and msg.get("reactions"):
                await apply_reactions(channel, sent, msg["reactions"])
        except discord.HTTPException as e:
            if e.status == 429:
                retry_after = getattr(e, "retry_after", 5)
                print(f"Rate limited, sleeping {retry_after}s")
                await asyncio.sleep(retry_after)
                try:
                    sent = await send_message(webhook, msg)
                except discord.HTTPException as e2:
                    success = False
                    print(f"Failed message {msg['id']} after retry, will retry on next run: {e2}")
            else:
                success = False
                print(f"Failed message {msg['id']}, will retry on next run: {e}")

        if success:
            done_ids.add(msg["id"])
        if i % 20 == 0 or i == len(remaining):
            save_progress(progress_path, done_ids)
            print(f"Progress: {len(done_ids)}/{total}")

        await asyncio.sleep(DELAY_SECONDS)

    print("Import complete.")
    await bot.close()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


def main():
    if len(sys.argv) != 2:
        print(f"Usage: python {sys.argv[0]} <messages.jsonl>")
        sys.exit(1)
    if not TOKEN or not CHANNEL_ID:
        print("Set DISCORD_BOT_TOKEN and TARGET_CHANNEL_ID in your .env file.")
        sys.exit(1)

    jsonl_path = sys.argv[1]

    async def runner():
        async with bot:
            asyncio.create_task(run_import(jsonl_path))
            await bot.start(TOKEN)

    asyncio.run(runner())


if __name__ == "__main__":
    main()
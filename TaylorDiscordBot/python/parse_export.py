import json
import sys
from bs4 import BeautifulSoup


def clean_text(node):
    if node is None:
        return ""
    for br in node.find_all("br"):
        br.replace_with("\n")
    for quote in node.select(".chatlog__markdown-quote-content"):
        quote.insert_before("> ")
    return node.get_text().strip()


def parse_attachments(container):
    attachments = []
    for a in container.select(".chatlog__attachment"):
        img = a.select_one(".chatlog__attachment-media")
        link = a.find("a", href=True)
        url = None
        if img and img.get("src"):
            url = img["src"]
        elif link:
            url = link["href"]
        if url:
            attachments.append(url)
    return attachments


def resolve_media_url(el, src_attr="src"):
    if el is None:
        return None
    return el.get("data-canonical-url") or el.get(src_attr)


def parse_embed(embed_div):
    data = {}

    author = embed_div.select_one(".chatlog__embed-author")
    if author:
        data["author"] = author.get_text(strip=True)

    title = embed_div.select_one(".chatlog__embed-title")
    if title:
        link = title.find("a", href=True)
        data["title"] = title.get_text(strip=True)
        data["url"] = link["href"] if link else None

    desc = embed_div.select_one(".chatlog__embed-description")
    if desc:
        data["description"] = desc.get_text(strip=True)

    thumb_url = resolve_media_url(embed_div.select_one(".chatlog__embed-thumbnail"))
    if thumb_url:
        data["thumbnail"] = thumb_url

    images = [resolve_media_url(img) for img in embed_div.select(".chatlog__embed-image")]
    images = [u for u in images if u]
    if images:
        data["image"] = images[0]
        if len(images) > 1:
            data["extra_images"] = images[1:]

    # bare image embeds
    generic_image_url = resolve_media_url(embed_div.select_one(".chatlog__embed-generic-image"))
    if generic_image_url and not data.get("image"):
        data["image"] = generic_image_url

    # video / gif embeds
    video_el = embed_div.select_one("video")
    if video_el:
        source = video_el.find("source")
        video_url = video_el.get("data-canonical-url") or (
            source.get("src") if source else None
        )
        if video_url:
            data["video"] = video_url

    color_pill = embed_div.select_one(".chatlog__embed-color-pill")
    if color_pill and color_pill.get("style"):
        style = color_pill["style"]
        if "rgba(" in style:
            nums = style.split("rgba(")[1].split(")")[0].split(",")
            try:
                r, g, b = (int(nums[0]), int(nums[1]), int(nums[2]))
                data["color"] = (r << 16) + (g << 8) + b
            except (ValueError, IndexError):
                pass

    footer = embed_div.select_one(".chatlog__embed-footer")
    if footer:
        data["footer"] = footer.get_text(strip=True)

    return data if any(v for v in data.values()) else None


def parse_reactions(container):
    reactions = []
    for r in container.select(".chatlog__reaction"):
        count_el = r.select_one(".chatlog__reaction-count")
        count = int(count_el.get_text(strip=True)) if count_el else 1
        emoji_img = r.select_one("img.chatlog__emoji")
        if emoji_img and emoji_img.get("alt"):
            emoji = emoji_img["alt"]
        else:
            emoji = r.get_text(strip=True)
        reactions.append({"emoji": emoji, "count": count})
    return reactions


def parse_reply(container):
    reply = container.select_one(".chatlog__reply")
    if not reply:
        return None
    author = reply.select_one(".chatlog__reply-author")
    content = reply.select_one(".chatlog__reply-content")
    return {
        "author": author.get_text(strip=True) if author else None,
        "content": content.get_text(strip=True) if content else None,
    }


def parse(html_path):
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "lxml")

    messages = []

    for group in soup.select(".chatlog__message-group"):
        current_author = None
        current_username = None
        current_avatar = None
        current_color = None

        for container in group.select(".chatlog__message-container"):
            msg_id = container.get("data-message-id")

            header = container.select_one(".chatlog__header")
            if header:
                author_el = header.select_one(".chatlog__author")
                if author_el:
                    current_author = author_el.get_text(strip=True)
                    current_username = author_el.get("title") or current_author
                    style = author_el.get("style", "")
                    if "color:" in style:
                        current_color = style.split("color:")[1].split(";")[0].strip()
                avatar_el = container.select_one(".chatlog__avatar")
                if avatar_el and avatar_el.get("src"):
                    current_avatar = avatar_el["src"]

            ts_el = container.select_one(".chatlog__timestamp, .chatlog__short-timestamp")
            timestamp = ts_el.get("title") if ts_el else None

            content_el = container.select_one(".chatlog__content")
            content = clean_text(content_el)

            attachments = parse_attachments(container)

            embeds = []
            for embed_div in container.select(".chatlog__embed"):
                parsed = parse_embed(embed_div)
                if parsed:
                    embeds.append(parsed)

            reply = parse_reply(container)
            reactions = parse_reactions(container)

            if not (content or attachments or embeds):
                # system notifications / empty containers
                sys_el = container.select_one(".chatlog__system-notification-content")
                if sys_el:
                    content = sys_el.get_text(strip=True)
                else:
                    continue

            messages.append(
                {
                    "id": msg_id,
                    "author": current_author,
                    "author_username": current_username,
                    "author_color": current_color,
                    "avatar_url": current_avatar,
                    "timestamp": timestamp,
                    "content": content,
                    "attachments": attachments,
                    "embeds": embeds,
                    "reply": reply,
                    "reactions": reactions,
                }
            )

    return messages


def main():
    if len(sys.argv) != 3:
        print(f"Usage: python {sys.argv[0]} <export.html> <output.jsonl>")
        sys.exit(1)

    html_path, out_path = sys.argv[1], sys.argv[2]
    messages = parse(html_path)

    with open(out_path, "w", encoding="utf-8") as f:
        for m in messages:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")

    print(f"Parsed {len(messages)} messages -> {out_path}")


if __name__ == "__main__":
    main()
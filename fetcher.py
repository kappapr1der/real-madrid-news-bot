import aiohttp
import feedparser
import asyncio

async def fetch_news(url):
    news_items = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                text = await resp.text()
                feed = feedparser.parse(text)
                for entry in feed.entries:
                    news_items.append({
                        "title": entry.title,
                        "link": entry.link,
                        "published": entry.get("published_parsed", None),
                        "summary": getattr(entry, "summary", "")
                    })
    except Exception as e:
        print(f"Error fetching {url}: {e}")
    return news_items

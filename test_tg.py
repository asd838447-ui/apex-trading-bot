import asyncio
from server.skills.skill_04_nlp import scrape_telegram_channel

async def main():
    res = await scrape_telegram_channel("durov")
    for r in res[:2]:
        print(r["text"][:50].encode('utf-8'))

if __name__ == "__main__":
    asyncio.run(main())

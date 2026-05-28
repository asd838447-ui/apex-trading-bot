import aiohttp
import asyncio

async def test_cryptocompare():
    url = "https://min-api.cryptocompare.com/data/v2/news/?categories=BTC"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            print("Status:", resp.status)
            data = await resp.json()
            if data and "Data" in data:
                for item in data["Data"][:3]:
                    print("-", item["title"])
            else:
                print("No data", data)

if __name__ == "__main__":
    asyncio.run(test_cryptocompare())

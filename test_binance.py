import asyncio
from server.skills.skill_03_onchain import get_quant_alphas_real

async def test():
    result = await get_quant_alphas_real("BTCUSDT")
    print(result)

if __name__ == "__main__":
    asyncio.run(test())

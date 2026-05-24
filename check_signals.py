import asyncio
import json
from server.config import settings
from server.tasks.state import market_state

async def main():
    await market_state.initialize_if_needed()
    print("KEYS IN MULTI_SIGNALS:", market_state.multi_signals.keys())
    for k, v in market_state.multi_signals.items():
        print(f"SYMBOL {k}: has {len(v.get('skills', []))} skills")

asyncio.run(main())

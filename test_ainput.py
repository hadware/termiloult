from aioconsole import ainput
import asyncio

async def sleep_and_talk(times):
    for i in range(times):
        await asyncio.sleep(1)
        print("WESH")

async def some_coroutine():
    while True:
        line = await ainput(">>> ")
        print(line)

loop = asyncio.get_event_loop()
# asyncio.get_event_loop().run_until_complete(some_coroutine())
asyncio.ensure_future(some_coroutine())
asyncio.ensure_future(sleep_and_talk(10))
asyncio.get_event_loop().run_forever()

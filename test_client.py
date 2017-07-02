import json
from asyncio import get_event_loop

import websockets

from audiosink import AudioSink


async def client():
    sink = AudioSink()
    async with websockets.connect("wss://loult.family/socket/") as ws:
        while True:
            data = await ws.recv()
            if isinstance(data, bytes):
                sink.add(data)
            else:
                print(json.loads(data))

loop = get_event_loop()
loop.run_until_complete(client())

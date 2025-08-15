import asyncio
import json
import websockets
import traceback

# I don't know what I'm doing yet
# Bare bones stuff, not actually implemented

async def main(follow_queue):
    async def handler(websocket, path):
        websocket.send(follow_queue.get())

    try:
        async with websockets.serve(handler, "localhost", 8002):
            await asyncio.Future()
    except Exception as e:
        print("An exception occured:", e)
        traceback.print_exc()

def pre_main(follow_queue):
    asyncio.run(main(follow_queue))

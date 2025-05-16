import asyncio
import socketio
import json
import aioconsole
from dotenv import load_dotenv

load_dotenv()

global_gameplay_queue = None
sio = socketio.AsyncClient()

async def get_input():
    while True:
        user_input = input("Num between 0 - 500? ")
        global_gameplay_queue.put(user_input)
        print(f"{global_gameplay_queue.qsize()=}")
        await asyncio.sleep(0.1)

async def handler():
    while True:
        command = await aioconsole.ainput("Num between 0 - 500? ")
        await asyncio.sleep(0.1)
        command = command.strip().lower()
        print(f"{command=}")
        global_gameplay_queue.put(command)
        print(f"{global_gameplay_queue.qsize()=}")
        #
        if global_gameplay_queue.qsize() > 0:
            val = global_gameplay_queue.get()
            print(f"{val=}")
            client_msg = f'{{ "side": "right", "y": {val} }}'
            client_msg={"side": "right", "y": val }
            print(f"{client_msg=}")
            await sio.emit('paddleMove', client_msg)
        await asyncio.sleep(0.1)

@sio.event
async def connect():
    print('Connected to server')
    asyncio.create_task(handler())

@sio.event
async def gameState(data):
    try:
        pass
    except Exception as e:
        print(repr(e))
        print(data)
        raise(e)

@sio.event
async def disconnect():
    print('Disconnected from server')

async def main():
    try:
        await sio.connect('http://localhost:3000')
        await sio.wait()
    except KeyboardInterrupt:
        await sio.disconnect()

async def test_main():
    import multiprocessing
    global global_gameplay_queue
    global_gameplay_queue = multiprocessing.Queue()
    await main()

if __name__ == "__main__":
    try: 
        asyncio.run(test_main())
    except KeyboardInterrupt:
        print('[❗] Application interrupted. Shutting down...')
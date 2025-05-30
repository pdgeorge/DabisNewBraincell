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

async def send_paddleMove(side, pos):
    # client_msg = f'{{ "side": "{side}", "y": {pos} }}'
    client_msg={"side": side, "y": pos }
    print(client_msg)
    await sio.emit('paddleMove', client_msg)

async def send_right_paddle(pos):
    if isinstance(pos, int):
        if pos < 0:
            pos = 0
        if pos > 500:
            pos = 500
    else:
        pos = 0
    await send_paddleMove("right", pos)

async def send_left_paddle(pos):
    if isinstance(pos, int):
        if pos < 0:
            pos = 0
        if pos > 500:
            pos = 500
    else:
        pos = 0
    await send_paddleMove("left", pos)

async def send_reset(client_msg):
    await sio.emit('reset', client_msg)

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
            print(f"{val[0]}")
            print(f"{str(val[0]).upper()}")
            if val == "reset":
                client_msg = val
                await send_reset(client_msg)
            elif str(val[0]).upper() == "R":
                val = val[1:]
                await send_right_paddle(val)
            elif str(val[0]).upper() == "L":
                val = val[1:]
                await send_left_paddle(val)
        await asyncio.sleep(0.1)

@sio.event
async def connect():
    print('Connected to server')
    asyncio.create_task(handler())

@sio.event
async def gameState(data):
    try:
        if data['paddles']['left']['score'] > 0 or data['paddles']['right']['score'] > 0:
            print(f"Score changed! L: {data['paddles']['left']['score']} | R: {data['paddles']['right']['score']}")
            print(f"{data['ball']['y']=}")
            print(f"{data['ball']['x']=}")
            print(f"{data['ball']['dx']=}")
            print(f"{data['ball']['dy']=}")
            if data['ball']['x'] < 400:
                await send_left_paddle(data['ball']['y'] - 50)
            if data['ball']['x'] > 400:
                await send_right_paddle(data['ball']['y'] - 50)
        
        if not any(block['active'] for block in data['blocks']):
            print("All blocks destroyed!")
            await send_reset("reset")
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
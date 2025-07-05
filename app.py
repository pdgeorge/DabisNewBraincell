# dabibody
# This is the main server, it reaches out to other parts to do things.
# This is the body of dabi. "dabibody". It asks other parts things, gets answers.
# It is a central hub of action.

import asyncio
import json
from websocket import create_connection
import websockets
from websockets.sync.client import connect
import sqlite3
import numpy as np
from pydub import AudioSegment
from dabi_logging import dabi_print

import random
import traceback

from bot_openai import OpenAI_Bot

TEMPLATE = {
    "type": "updateMouth",
    "duration": 0,
    "pattern": [],
    "message": ""
}

TIME_BETWEEN_SPEAKS = 10

CABLE_A_OUTPUT = 26 # This was found using dabi.scan_audio_devices()

global_speaking_queue = None
global_game_queue = None

async def db_insert(table_name, username, message, response):
    # Connect to the db. If it doesn't exist it will be created.
    db_name = 'dabibraincell.db'
    conn = sqlite3.connect(db_name)
    cur = conn.cursor()
    table_columns = 'id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, message TEXT NOT NULL, response TEXT NOT NULL'
    create_table_query = f'CREATE TABLE IF NOT EXISTS {table_name} ({table_columns})'
    cur.execute(create_table_query)
    
    # Insert the entry
    insert_query = f'INSERT INTO {table_name} (username, message, response) VALUES (?, ?, ?)'
    cur.execute(insert_query, (username, message, response))
    
    # Commit and close
    conn.commit()
    conn.close()
    
# Process the audio to receive an array of values between 0 and 1 for amplitude
def process_audio(audio_path, interval=1):
    
    amplitude_values = []
    audio = AudioSegment.from_file(audio_path)

    # Convert the audio to a numpy array
    y = np.array(audio.get_array_of_samples())

    # Ensure the audio is in the correct format (convert to mono if necessary)
    if audio.channels > 1:
        y = y.reshape((-1, audio.channels)).mean(axis=1)

    sr = audio.frame_rate
    samples_per_interval = int(sr * interval)
    num_intervals = int(np.ceil(len(y) / samples_per_interval))

    # Extract amplitude values at each interval
    for i in range(num_intervals):
        start_sample = i * samples_per_interval
        end_sample = min((i + 1) * samples_per_interval, len(y))
        interval_amplitude = np.mean(np.abs(y[start_sample:end_sample]))
        amplitude_values.append(interval_amplitude)

    # Normalize the amplitude values to range between 0 and 1
    max_amplitude = max(amplitude_values)
    normalized_amplitude_values = [amp / max_amplitude for amp in amplitude_values]
    rounded_values = [round(float(value), 3) for value in normalized_amplitude_values]

    return rounded_values

async def reset(dabi):
    dabi.reset_memory()
    return "Successfully reset memory, Wakey Wakey Dabi!"

async def choose_action(msg, dabi):
    dabi_print(msg)
    if 'reset' in msg:
        return await reset(dabi)

# Takes in the message received from twitch_connector
# Removes "twitch:" and "speaks" the message
async def speak_message(message, dabi):
    to_send = None
    #
    twitch_prefix = "twitch:"
    game_prefix = "game:"
    action_prefix = "action:"
    if message["formatted_msg"].startswith(twitch_prefix):
        send_to_dabi = message["formatted_msg"][len(twitch_prefix):]
    if message["formatted_msg"].startswith(game_prefix):
        send_to_dabi = message["formatted_msg"][len(game_prefix):]
    if message["formatted_msg"].startswith(action_prefix):
        send_to_dabi = await choose_action(message["formatted_msg"][len(twitch_prefix):], dabi)
    
    response = await dabi.send_msg(send_to_dabi)
    dabi_print(f"{response=}")
    if message["msg_server"].isdigit() != True:
        await db_insert(table_name=message["msg_server"], username=message["msg_user"], message=message["msg_msg"], response=response)
    
    voice_path, voice_duration = dabi.create_se_voice(dabi.se_voice, response)
    
    # Need to add in "template" and how it wil be sent in to_send below
    to_send = TEMPLATE
    pattern = process_audio(voice_path)
    to_send["pattern"] = pattern
    to_send["message"] = response
    to_send = json.dumps(to_send)
    return to_send, voice_path, voice_duration

async def send_msg_helper(queue, websocket, dabi, speaking_queue):
    to_send = None
    message = queue.get()
    
    message = json.loads(message)
    # message = check_for_command(message, dabi)
    to_send, voice_path, voice_duration = await speak_message(message, dabi)
    
    # websockets.broadcast(websockets=CLIENTS, message=to_send)
    await websocket.send(to_send)
    
    # dabi.read_message_choose_device_mp3(voice_path, CABLE_A_OUTPUT)
    speaking_queue.put(voice_path)
    await asyncio.sleep(voice_duration + TIME_BETWEEN_SPEAKS)

async def send_msg(websocket, path, dabi, input_msg_queue, game_queue, speaking_queue):
    if input_msg_queue.qsize() > 0:
        await send_msg_helper(queue=input_msg_queue, websocket=websocket, dabi=dabi, speaking_queue=speaking_queue)
    if game_queue.qsize() > 0:
        await send_msg_helper(queue=game_queue, websocket=websocket, dabi=dabi, speaking_queue=speaking_queue)
        

def load_new_personality(dabi, personality_to_load):
    dabi_print("Load_new_personality")
    dabi_name, dabi_voice, dabi_system = load_personality(personality_to_load)
    dabi.bot_name = dabi_name
    dabi.voice = dabi_voice
    dabi.temp_system_message["content"] = dabi_system
    dabi.reset_memory()
    

def load_personality(personality_to_load):
    name_to_return = None
    voice_to_return = None
    personality_to_return = None
    base_system = None
    with open("system.json", "r") as f:
        data = json.load(f)
        
    name_to_return = data["name"]
    voice_to_return = data["voice"]
    base_system = data["system"]
    for personality in data.get("personalities"):
        if personality.get("personality") == personality_to_load:
            personality_to_return = personality.get("system", None)
            break
        if personality_to_return is None:
            personality_to_return = data.get("personalities")[0].get("system", None)
    personality_to_return = base_system + personality_to_return
    
    return name_to_return, voice_to_return, personality_to_return

async def main(input_msg_queue, game_queue, speaking_queue):
    dabi_name, dabi_voice, dabi_system = load_personality("mythicalmentor")
    dabi = OpenAI_Bot(bot_name=dabi_name, system_message=dabi_system, voice=dabi_voice)

    # Reminder to self: 
    # Need to have "A" websocket connection or this won't work.
    async def handler(websocket, path):
        await send_msg(websocket, path, dabi, input_msg_queue, game_queue, speaking_queue)
    
    try:
        async with websockets.serve(handler, "localhost", 8001):
            await asyncio.Future()
    except Exception as e:
        # error_msg = "./error.mp3"
        # dabi.read_message_choose_device_mp3(error_msg, CABLE_A_OUTPUT)
        dabi_print("An exception occured:", e)
        traceback.print_exc()
          
def pre_main(input_msg_queue, game_queue, speaking_queue):
    global global_speaking_queue
    global_speaking_queue = speaking_queue
    global global_game_queue
    global_game_queue = game_queue
    asyncio.run(main(input_msg_queue, game_queue, speaking_queue))

if __name__ == "__main__":
    print("=========================================================")
    print("Do not run this solo any more.\nRun this through main.py")
    print("=========================================================")
    exit(0)
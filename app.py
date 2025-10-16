# dabibody
# This is the main server, it reaches out to other parts to do things.
# This is the body of dabi. "dabibody". It asks other parts things, gets answers.
# It is a central hub of action.

import asyncio
import json
# from websocket import create_connection
import websockets
# from websockets.sync.client import connect
import sqlite3
import numpy as np
from pydub import AudioSegment
from dabi_logging import dabi_print
import demoji
import traceback
from event_bus import EventBus, ensure_broker

TEMPLATE = {
    "type": "updateMouth",
    "duration": 0,
    "pattern": [],
    "message": ""
}

TIME_BETWEEN_SPEAKS = 10

global_speaking_queue = None
global_game_queue = None
read_chat_flag = False
last_msg_time = None
chat_messages = []

def remove_emoji(text):
    found = demoji.findall(text)
    for item in found.keys():
        text = text.replace(item, "")
    return text

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
        print("===resetting===")
        return await reset(dabi)
    if 'personality' in msg:
        print("!!!Load personalidy found!!!")
        personality_prefix = "action:personality:"
        personality_to_load = msg[len(personality_prefix):]
        dabi.load_new_personality(dabi, personality_to_load)
        return_string = f"Reawakening as {personality_to_load}"
        return return_string

# Takes in the message received from twitch_connector
# Removes "twitch:" and "speaks" the message
async def speak_message(message, dabi):
    to_send = None
    response = ""
    
    twitch_prefix = "twitch:"
    game_prefix = "game:"
    action_prefix = "action:"
    website_prefix = "website:"
    discord_prefix = "discord:"
    message_prefix = "message:"
    react_prefix = "react:"
    if message.get("formatted_msg", "").startswith(twitch_prefix):
        send_to_dabi = message.get("formatted_msg", "")[len(twitch_prefix):]
        response = await dabi.send_msg(send_to_dabi)
    if message.get("formatted_msg", "").startswith(game_prefix):
        send_to_dabi = message.get("formatted_msg", "")[len(game_prefix):]
        response = await dabi.send_msg(send_to_dabi)
    if message.get("formatted_msg", "").startswith(website_prefix):
        send_to_dabi = message.get("formatted_msg", "")[len(website_prefix):]
        response = await dabi.send_msg(send_to_dabi)
    if message.get("formatted_msg", "").startswith(discord_prefix):
        send_to_dabi = message.get("formatted_msg", "")[len(discord_prefix):]
        response = await dabi.send_msg(send_to_dabi)
    if message.get("formatted_msg", "").startswith(action_prefix):
        send_to_dabi = await choose_action(message.get("formatted_msg", "")[len(action_prefix):], dabi)
        response = await dabi.send_msg(send_to_dabi)
    if message.get("formatted_msg", "").startswith(message_prefix) and read_chat_flag:
        send_to_dabi = message.get("formatted_msg", "")[len(message_prefix):]
        response = await dabi.send_msg(send_to_dabi)
    if message.get("formatted_msg", "").startswith(react_prefix):
        send_to_dabi_img = message["file_name"]
        send_to_dabi_msg = message.get("formatted_msg", "")[len(react_prefix):]
        response = await dabi.send_img(send_to_dabi_img, send_to_dabi_msg)
    else:
        print("Bro, we couldn't find anything.")
        print("Are you testing something?")
        print(f"Either way, here's the\nmessage\n===\n{message=}\n===\nthat we started with")
        response = "We're testing stuff here"

    dabi_print(f"{response=}")

    response = remove_emoji(response)
    
    voice_path, voice_duration = dabi.create_se_voice(dabi.se_voice, response)
    
    # Need to add in "template" and how it wil be sent in to_send below
    to_send = TEMPLATE
    pattern = process_audio(voice_path)
    to_send["pattern"] = pattern
    to_send["message"] = response
    to_send = json.dumps(to_send)
    return to_send, voice_path, voice_duration

async def send_msg(queue, dabi, speaking_queue, event):
    """Process one event and speak it."""
    to_send = None

    message = event.get("data", {})
    print(f"\n\napp.py 162?")
    print(f"{message=}\n")
    
    print(f"{message=}")
    print(f"{type(message)=}")
    if isinstance(message, str):
        try:
            message = json.loads(message)
        except Exception as e:
            print("Bas JSON event:", e, message)

    # message = check_for_command(message, dabi)
    to_send, voice_path, voice_duration = await speak_message(message, dabi)
    
    # dabi.read_message_choose_device_mp3(voice_path, CABLE_A_OUTPUT)
    speaking_queue.put(voice_path)
    await asyncio.sleep(voice_duration + TIME_BETWEEN_SPEAKS)

async def main(input_msg_queue, game_queue, speaking_queue, dabi):
    print(f"{dabi.bot_name=}")
    bus = await ensure_broker()
    q = await bus.bind_queue(queue_name="app", pattern="#") # Will do ALL redeems
    print(f"Connected")

    try:
        async with q.iterator() as it:
            async for msg in it:
                try:
                    event = json.loads(msg.body)
                    print(f"{event=}")
                except Exception as e:
                    print("Bas JSON event:", e, msg.body)
                    continue

                print(f"\n194\n{event=}\n")
                await send_msg(queue=input_msg_queue, dabi=dabi, speaking_queue=speaking_queue, event=event)

    except Exception as e:
        dabi_print("An exception occured:", e)
        traceback.print_exc()
          
def pre_main(input_msg_queue, game_queue, speaking_queue, dabi):
    global global_speaking_queue
    global_speaking_queue = speaking_queue
    global global_game_queue
    global_game_queue = game_queue
    asyncio.run(main(input_msg_queue, game_queue, speaking_queue, dabi))

def pre_pre_main():
    from bot_openai import OpenAI_Bot, load_personality
    dabi_name, dabi_voice, dabi_system = load_personality()
    dabi = OpenAI_Bot(bot_name=dabi_name, system_message=dabi_system, voice=dabi_voice)
    pre_main(None, None, None, dabi)

if __name__ == "__main__":
    print("=========================================================")
    print("Do not run this solo any more.\nRun this through main.py")
    print("=========================================================")
    # exit(0)
    pre_pre_main()
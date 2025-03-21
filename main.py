import asyncio
import multiprocessing
import time
import twitch_event
import discord_bot
import app
from dotenv import load_dotenv

# Acronyms:
# TTT = Text To Text. LLM text transformation, text in, text out.
# TTS = Text To Speech. Text in, Audio out.
# STT = Speech To Text. Audio in, Text out.

# Historical test/example
def print_test(queue):
    while True:
        if queue.qsize() > 0:
            message = queue.get()
            print(f"main.py print_twitch: {message=}")
        else:
            time.sleep(1)

async def main():
    try:
        ### QUEUES ###
        twitch_queue = multiprocessing.Queue() # Messages to process for TTT before passing to TTS
        discord_queue = multiprocessing.Queue() # Messages to TTS

        ### INGESTORS ###
        listen_to_chat = False # Change whether you want Dabi to listen to chat messages or not
        event_process = multiprocessing.Process(target=twitch_event.start_events, args=(twitch_queue, listen_to_chat,))
        event_process.start()

        discord_process = multiprocessing.Process(target=discord_bot.start_bot, args=(twitch_queue,discord_queue,))
        discord_process.start()
        
        ### MAIN APP ###
        app_process = multiprocessing.Process(target=app.pre_main, args=(twitch_queue,discord_queue,))
        app_process.start()

    except KeyboardInterrupt as kb_interrupt:
        print(f"[!] Keyboard interrupt.\n{kb_interrupt}")
        event_process.join()
        event_process.terminate()
        event_process.close()
        
        discord_process.join()
        discord_process.terminate()
        discord_process.close()
        
        app_process.join()
        app_process.terminate()
        app_process.close()
    
if __name__ == "__main__":
    asyncio.run(main())

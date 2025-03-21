# https://guide.pycord.dev/voice/receiving
import discord
import os
import json
# from discord.ext import commands
from dotenv import load_dotenv
# import tbone_transcriber
import asyncio

from pydub import AudioSegment

load_dotenv()

DISCORD_TOKEN = os.environ.get('CYRA_DISCORD')

# Create the bot
intents = discord.Intents.all()
intents.message_content = True
bot = discord.Bot()
connections = {}
time_to_listen = 10

global_twitch_queue = None
global_discord_queue = None
global_comminicating = False

@bot.event
async def on_ready():
    print(f"{bot.user} is ready and online!")

@bot.slash_command(name="hello", description="Say hello to the bot!")
async def hello(ctx: discord.ApplicationContext):
    await ctx.respond("Hey!")

@bot.slash_command(name='ping', description="Ping from Cyra")
async def ping(ctx: discord.ApplicationContext):
    await ctx.respond("pong")

@bot.slash_command()
async def play(ctx: discord.ApplicationContext, file_to_play: str = discord.Option(description="Enter the new time in seconds", min=1, max=999)):
    await ctx.respond(f"You are currently in {ctx.author.voice.channel.name}")
    voice = ctx.author.voice
    if not voice:
        return await ctx.respond("You aren't in a voice channel!")
    if not ctx.voice_client:
        vc = await voice.channel.connect()  # Connect to the voice channel the author is in.
    else:
        vc = ctx.voice_client
    connections.update({ctx.guild.id: vc})  # Updating the cache with the guild and channel.
    try:
        # if global_discord_queue.qsize() > 0:
            # to_play = global_discord_queue.get()
        vc.stop()
        print("Before calling vc.play")
        vc.play(discord.FFmpegPCMAudio(file_to_play))
        print(f"Playing {file_to_play}")
        await ctx.respond(file_to_play)
        await asyncio.sleep(1)
    except Exception as e:
        print(f"Somebody tell George Dabi's braincell asploded: {e}")

@bot.slash_command()
async def discord_queue_length(ctx: discord.ApplicationContext):
    await ctx.respond(f"There are {global_discord_queue.qsize()} items in the discord queue.")

@bot.slash_command()
async def listen(ctx: discord.ApplicationContext):
    await ctx.respond(f"You are currently in {ctx.author.voice.channel.name}")
    voice = ctx.author.voice
    if not voice:
        return await ctx.respond("You aren't in a voice channel!")
    if not ctx.voice_client:
        vc = await voice.channel.connect()  # Connect to the voice channel the author is in.
    else:
        vc = ctx.voice_client
    connections.update({ctx.guild.id: vc})  # Updating the cache with the guild and channel.
    try:
        while True:
            if vc.is_playing():
                await asyncio.sleep(1)
            if global_discord_queue.qsize() > 0:
                print("==========vc.is_connected=========")
                print(f"{vc.is_connected()=}")
                print("==========vc.is_connected=========")
                to_play = global_discord_queue.get()
                vc.stop()
                vc.play(discord.FFmpegPCMAudio(to_play))
                to_delay = audio_length(to_play)
                print(f"Playing {to_play}, it is {to_delay} long")
                await asyncio.sleep(to_delay + 2)
                if os.path.exists(to_play):
                    os.remove(to_play)
                    print(f"{to_play} removed")
                else:
                    print(f"Unable to remove {to_play}")
                    await asyncio.sleep(0.1)
    except Exception as e:
        print(f"Somebody tell George Dabi's braincell asploded: {e}")

@bot.slash_command()
async def record(ctx: discord.ApplicationContext):  # If you're using commands.Bot, this will also work.
    await ctx.respond(f"You are currently in {ctx.author.voice.channel.name}")
    voice = ctx.author.voice
    if not voice:
        return await ctx.respond("You aren't in a voice channel!")
    if not ctx.voice_client:
        vc = await voice.channel.connect()  # Connect to the voice channel the author is in.
    else:
        vc = ctx.voice_client
    connections.update({ctx.guild.id: vc})  # Updating the cache with the guild and channel.

    vc.start_recording(
        discord.sinks.WaveSink(),  # The sink type to use.
        once_done,  # What to do once done.
        ctx.channel  # The channel to disconnect from.
    )
    await ctx.respond("Started recording!")
    await asyncio.sleep(time_to_listen)
    await stop_recording(ctx)

@bot.slash_command()
async def update_time(ctx: discord.ApplicationContext, new_time: int = discord.Option(description="Enter the new time in seconds", min=1, max=999)):
    global time_to_listen
    time_to_listen = new_time
    await ctx.respond(f"Updated time to {time_to_listen}")

@bot.slash_command()
async def stop_communicate(ctx: discord.ApplicationContext, stop: int = discord.Option(description="Should Dabi Stop?", min=0, max=1)):
    global global_comminicating
    await ctx.respond(f"{stop=}")
    if stop == 1:
        global_comminicating = True
        await ctx.respond(f"Dabi is non-stop")
    if stop == 0:
        global_comminicating = False
        await ctx.respond(f"Dabi is now stop")

@bot.slash_command()
async def communicate(ctx: discord.ApplicationContext):
    global global_comminicating
    voice = ctx.author.voice
    if not voice:
        return await ctx.respond("You aren't in a voice channel!")
    if not ctx.voice_client:
        vc = await voice.channel.connect()  # Connect to the voice channel the author is in.
    else:
        vc = ctx.voice_client
    connections.update({ctx.guild.id: vc})  # Updating the cache with the guild and channel.
    await ctx.respond("Time for some chatting!")
    try:
        global_comminicating = True
        while global_comminicating:
            await record(ctx)
            await asyncio.sleep(time_to_listen)
            await asyncio.sleep(0.1)
    except Exception as e:
        print(f"Somebody tell George there has been an error in my braincell: {e}")
        # TODO add a way for Dabi to scream that. Either once or loop it.

async def stop_recording(ctx: discord.ApplicationContext):
    if ctx.guild.id in connections:  # Check if the guild is in the cache.
        vc = connections[ctx.guild.id]
        vc.stop_recording()  # Stop recording, and call the callback (once_done).
        # del connections[ctx.guild.id]  # Remove the guild from the cache.
        # await ctx.delete()  # And delete.
        await ctx.respond("Done")
    else:
        await ctx.respond("I am currently not recording here.")  # Respond with this if we aren't recording.

# async def play(ctx):

async def save_files(files):
    saved_files = []
    for file in files:
        with open(file.filename, "wb") as f:
                f.write(file.fp.read())
                saved_files.append(file.filename)
    return saved_files

async def once_done(sink: discord.sinks, channel: discord.TextChannel, *args):  # Our voice client already passes these in.
    returned_transcription = {}
    saved_files = []
    recorded_users = [  # A list of recorded users
        f"<@{user_id}>"
        for user_id, audio in sink.audio_data.items()
    ]
    # await sink.vc.disconnect()  # Disconnect from the voice channel.
    
    files = [discord.File(audio.file, f"{user_id}.{sink.encoding}") for user_id, audio in sink.audio_data.items()]  # List down the files.
    for file in files:
        with open(file.filename, "wb") as f:
            f.write(file.fp.read())
            saved_files.append(file.filename)
        # await save_files(files)
    returned_transcription = "tbone_transcriber.transcriber(saved_files)"
    # print(f"d_b.py: pre loop: {returned_transcription}")
    for transcription in returned_transcription:
        print(f"d_b.py: for t in r_t: {transcription=}")

        # For Twitch
        transcription["formatted_msg"] = f"twitch:{transcription["msg_user"]}: {transcription["msg_msg"]}"
        transcription["msg_server"] = "pdgeorge"
        to_send = transcription

        print(f"{to_send=}")
        # Need to add in a basic "convert user ID to name" function here.
        # Don't need to hard code the things, can make it load from file for Discord ID/Name Key/Value pairs.
        global_twitch_queue.put(json.dumps(to_send))
        
    # Attempts to access transcription, even if nobody says anything.
    # Additionally, need to update this as a whole for when multiple people are talking or able to talk.
    # Potential option: Combine to one single message?
    await channel.send(f"Transcription for this message:\n\n{transcription["msg_msg"]}")  # Send a message with the transcription.

def audio_length(file):
    audio = AudioSegment.from_file(file)
    duration_seconds = len(audio) / 1000

    return duration_seconds

def start_bot(twitch_queue, discord_queue):
    global global_twitch_queue
    global global_discord_queue
    global_twitch_queue = twitch_queue
    global_discord_queue = discord_queue
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    # To run the bot quickly
    import multiprocessing
    twitch_queue = multiprocessing.Queue()
    discord_queue = multiprocessing.Queue()
    start_bot(twitch_queue, discord_queue)

    # For whatever we want to test.
    # asyncio.run(test())
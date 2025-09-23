import os
import asyncio
import threading
from io import BytesIO
import anyio
import tempfile
import json
import discord # Pycord 2.5+, `py-cord[voice]`
from discord.ext import commands, tasks
import whisper
from pathlib import Path
from pydub import AudioSegment
from dotenv import load_dotenv
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import urlparse
from urllib.request import urlopen
from dabi_logging import dabi_print

import whisper, torch
torch.set_num_threads(1)                     # don’t oversubscribe OpenMP

_MODEL = None

# --------- globals & constants ------------
load_dotenv()
DISCORD_TOKEN = os.getenv("CYRA_DISCORD")

DEFAULT_RECORD = 10
PRIVILEGED_ROLES = {"TheGuyInChargeIGuess", "Cyra-chatter"}

TMP_DIR = Path("./tmp"); TMP_DIR.mkdir(exist_ok=True)

DABISPIRATIONS = 1408392122649935913

# ----------  Discord client  ---------------
intents = discord.Intents.all()
intents.message_content = True
intents.voice_states = True

bot = discord.Bot(intents=intents)

# Helpers -------------------------------------------------

def _get_model():
    global _MODEL
    if _MODEL is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _MODEL = whisper.load_model("base", device=device)
    return _MODEL

def audio_length(path: str) -> float:
    """Return duration of an audio file (seconds) with pydub."""
    return len(AudioSegment.from_file(path)) / 1000.0

def _transcribe_sync(path: Path) -> str:
    model = _get_model()
    return model.transcribe(str(path))["text"].strip()

async def transcribe_async(path: Path, timeout: int = 120) -> str:
    """Public helper you can reuse anywhere in this module."""
    loop = asyncio.get_running_loop()
    return await asyncio.wait_for(
        loop.run_in_executor(None, _transcribe_sync, path),
        timeout=timeout
    )

async def do_transcribe(ctx: discord.ApplicationContext,
                        seconds: int):
    if not ctx.author.voice:
        return await ctx.respond("❌ You must be in a voice channel.", ephemeral=True)

    voice_channel = ctx.author.voice.channel
    # await ctx.respond(f"🎙️ Recording for **{seconds} s** …")

    # Connect or move to author’s channel
    vc: discord.VoiceClient
    if ctx.guild.voice_client:
        vc = ctx.guild.voice_client
        if vc.channel != voice_channel:
            await vc.move_to(voice_channel)
    else:
        vc = await voice_channel.connect()

    sink = discord.sinks.WaveSink()

    async def on_finish(sink: discord.sinks.Sink, *args):
        lines = []
        msg_usernames = []
        msg_msgs = []
        msg_server = 1337
        formatted_msgs = []
        for uid, audio in sink.audio_data.items():
            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                audio.file.seek(0)
                tmp.write(audio.file.read())
                wav_path = tmp.name

            text = (await transcribe_async(wav_path)).strip()
            os.unlink(wav_path)
            user = await bot.fetch_user(uid)
            msg_usernames.append(user.display_name)
            msg_msgs.append(text or "...silence")
            formatted_msgs.append(f"{user.display_name}: {text or '...silence'}")
            lines.append(f"{user.display_name}: {text or '…silence'}")

        formatted_msg = f'discord:{(" ".join(formatted_msgs) if formatted_msgs else "*No speech detected*")}'
        formatted_return = {
                "msg_user": (" ".join(msg_usernames) if msg_usernames else "*No speech detected*"),
                "msg_server": msg_server,
                "msg_msg": (" ".join(msg_msgs) if msg_msgs else "*No speech detected*"),
                "formatted_msg": formatted_msg
            }
        print(json.dumps(formatted_return))
        global_input_msg_queue.put(json.dumps(formatted_return))

    vc.start_recording(sink, on_finish)
    await asyncio.sleep(seconds)
    vc.stop_recording()                     # triggers on_finish

async def _resolve_dabispirations_channel():
    ch = bot.get_channel(DABISPIRATIONS)
    if isinstance(ch, discord.TextChannel):
        return ch
    
    for guild in bot.guilds:
        for ch in guild.text_channels:
            if ch.name.lower() == "dabispirations":
                return ch

async def _send_image_to_discord(image_bytes: bytes, filename: str, caption: str):
    channel = await _resolve_dabispirations_channel()
    if channel is None:
        raise RuntimeError("Couldn't find #dabispirations")
    
    file = discord.File(BytesIO(image_bytes), filename=filename)
    msg = await channel.send(content=caption or None, file=file)
    return {"message_id": msg.id, "channel_id": channel.id, "filename": filename}

def _load_personality(personality_to_load):
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

# --------- globals & constants ------------
discord_dabi = None
connections = {}
global_input_msg_queue = None
global_speaking_queue = None
listening_flag = False

@tasks.loop(seconds=60)
async def voice_keepalive():
    for vc in bot.voice_clients:
        if vc.is_connected():
            vc.send_audio_packet(b'\xF8\xFF\xFE', encode=False)

@bot.event
async def on_ready():
    dabi_print(f"{bot.user} is ready and online!")
    await bot.sync_commands()
    dabi_print("Slash commands synced.")
    # voice_keepalive.start()

@bot.event
async def on_message(message: discord.message):
    if message.author.bot:
        return

    if message.channel.name == "dabi-talks":
        if discord_dabi is not None:
            print(f"{message.content=}")
            dabi_response = await discord_dabi.send_msg(message.content)
            print(f"{dabi_response=}")
            await message.channel.send(f"{dabi_response}")
        else:
            await message.channel.send("Someone tell George Dabi Bork")

# @tasks.loop(seconds=60)
# async def voice_keepalive():
#     for vc in bot.voice_clients:
#         if vc.is_connected():
#             vc.send_audio_packet(b'\xF8\xFF\xFE', encode=False)

@bot.slash_command(name="hello", description="Say hello to the bot!")
@commands.has_any_role(*PRIVILEGED_ROLES)
async def hello(ctx: discord.ApplicationContext):
    await ctx.respond("Hello, world!")

@bot.slash_command(name="ping", description="Ping from Cyra!")
async def ping(ctx: discord.ApplicationContext):
    await ctx.respond("pong")

@bot.slash_command(name="queue_length", description="How many files are queued for playback?")
async def queue_length(ctx: discord.ApplicationContext):
    if global_speaking_queue is None:
        return await ctx.respond("Speaking queue not initialised", ephemeral=True)
    await ctx.respond(f"There are {global_speaking_queue.qsize()} items in the Discord queue.")

@bot.slash_command(name="test", description="Debug: show voice info")
async def test(ctx: discord.ApplicationContext):
    await ctx.respond(f"{ctx.author.voice=}, {ctx.guild.voice_client}")
    voice = ctx.author.voice
    if not voice:
        return
    vc = ctx.guild.voice_client or await voice.channel.connect()
    connections[ctx.guild.id] = vc
    
@bot.slash_command(name="listen", description="Play back items from the speaking queue")
@commands.has_any_role(*PRIVILEGED_ROLES)
async def listen(ctx: discord.ApplicationContext):
    global listening_flag
    voice = ctx.author.voice
    if not voice:
        return await ctx.respond("You aren't in a voice channel!")

    await ctx.respond(f"🎧 Listening … (voice channel **{voice.channel.name}**)")

    vc = ctx.guild.voice_client or await voice.channel.connect()
    connections[ctx.guild.id] = vc

    try:
        while True:
            if vc.is_playing():
                await asyncio.sleep(1)
                continue

            if global_speaking_queue and global_speaking_queue.qsize() > 0:
                temp_flag = listening_flag
                if listening_flag:
                    listening_flag = False
                to_play = global_speaking_queue.get()
                vc.stop()
                vc.play(discord.FFmpegPCMAudio(to_play))
                delay = audio_length(to_play) + 0.5
                dabi_print(f"Playing {to_play} ({delay:.1f}s)")
                await asyncio.sleep(delay)
                if temp_flag:
                    listening_flag = temp_flag
                temp_flag = False
                try:
                    os.remove(to_play)
                except OSError:
                    pass
            if listening_flag:
                print(f"{listening_flag=}")
                await do_transcribe(ctx=ctx, seconds=DEFAULT_RECORD)
                await asyncio.sleep(0.1)
            await asyncio.sleep(0.1)
    except Exception as e:
        dabi_print(f"Error in listen loop: {e}")

@bot.slash_command(name="transcribe", description="Record and transcribe this voice channel")
@commands.has_any_role(*PRIVILEGED_ROLES)
async def transcribe(
    ctx: discord.ApplicationContext,
    seconds: discord.Option(int, "Seconds to record (1-120)", default=DEFAULT_RECORD, min_value=1, max_value=120) # type: ignore
):
    await ctx.respond("One shot transcribe starting!")
    await do_transcribe(ctx=ctx, seconds=seconds)

@bot.slash_command(name="start_listening", description="Start listening")
@commands.has_any_role(*PRIVILEGED_ROLES)
async def start_listening(ctx: discord.ApplicationContext):
    global listening_flag
    listening_flag = True
    await ctx.respond("Will now listen and transcribe")

@bot.slash_command(name="stop_listening", description="Stop listening")
@commands.has_any_role(*PRIVILEGED_ROLES)
async def stop_listening(ctx: discord.ApplicationContext):
    global listening_flag
    listening_flag = False
    await ctx.respond("Will now stop listening and transcribing")

@bot.slash_command(name="test_listening", description="Stop listening")
@commands.has_any_role(*PRIVILEGED_ROLES)
async def test_listening(ctx: discord.ApplicationContext):
    global listening_flag
    await ctx.respond(f"listening_flag is {listening_flag}")

def start_receiving(
        *,
        host: str = "0.0.0.0",
        port: int = 9000,
        log_level: str = "info",
    ) -> None:

    app = FastAPI(title="Discord Event Receiver", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )

    @app.get("/health")
    async def health() -> dict[str, str]:  # noqa: D401 – simple verb is fine
        """Lightweight health-check endpoint for load balancers."""
        """
        For testing, use the following curl command, remember to update url and port as needed:
        curl -X GET http://0.0.0.0:8002/health
        """
        return {"status": "ok, Discord"}
    
    uvicorn.run(app, host=host, port=port, log_level=log_level, access_log=True)

def build_app() -> FastAPI:
    app = FastAPI(title="Discord Event Receiver", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )

    @app.get("/health")
    async def health() -> dict[str, str]:  # noqa: D401 – simple verb is fine
        """Lightweight health-check endpoint for load balancers."""
        """
        For testing, use the following curl command, remember to update url and port as needed:
        curl -X GET http://0.0.0.0:8002/health
        """
        return {"status": "ok, Discord"}
    
    @app.get("/image")
    async def post_image_to_dabispirations(
        path = Query(default=None, description="Absolute path on this machine to an image file"),
        url  = Query(default=None, description="HTTP(S) URL to an image"),
        caption = Query(default=None, description="Optional caption to include with the image"),
        filename = Query(default=None, description="Override filename shown in Discord"),
    ):
        """
        Trigger: GET /image?path=/abs/file.png&caption=Hello
                GET /image?url=https://example.com/pic.jpg&caption=Yo
        Effect: Posts the image to #dabispirations via the Discord bot.
        Note: This endpoint performs a side effect; consider making it POST in production.
        """
        if not path and not url:
            raise HTTPException(status_code=400, detail="Provide either 'path' or 'url'")

        # Load bytes (off the event loop)
        if path:
            p = Path(path)
            if not (p.exists() and p.is_file()):
                raise HTTPException(status_code=400, detail=f"Path not found or not a file: {path}")
            image_bytes = await anyio.to_thread.run_sync(p.read_bytes)
            fname = filename or p.name
        else:
            # Basic fetch with stdlib; keep it simple (use POST+UploadFile if you want streaming/validation)
            def _fetch():
                with urlopen(url) as r:  # nosec - trusted internal use; secure in production
                    return r.read()
            try:
                image_bytes = await anyio.to_thread.run_sync(_fetch)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to fetch url: {e}")
            parsed = urlparse(url)
            fname = filename or Path(parsed.path).name or "image"

        # Hand off to the Discord bot's loop and wait for result
        try:
            fut = asyncio.run_coroutine_threadsafe(
                _send_image_to_discord(image_bytes, fname, caption),
                bot.loop
            )
            result = await anyio.to_thread.run_sync(lambda: fut.result(timeout=20))
            return {"status": "ok", **result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to post image: {e}")

    # All new posts need to be before this
    return app



def start_receiving_in_thread():
    t = threading.Thread(target=lambda: uvicorn.run(build_app(), host="127.0.0.1", port=8002, log_level="info"), daemon=True)
    t.start()
    return t

def start_bot(input_msg_queue, speaking_queue, dabi):
    global global_input_msg_queue, global_speaking_queue, discord_dabi
    discord_dabi = dabi
    global_input_msg_queue = input_msg_queue
    global_speaking_queue = speaking_queue
    start_receiving_in_thread()
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    # quick local test run
    import multiprocessing
    from bot_openai import OpenAI_Bot, load_personality
    dabi_name, dabi_voice, dabi_system = load_personality("mythicalmentor")
    discord_dabi = OpenAI_Bot(bot_name=dabi_name, system_message=dabi_system, voice=dabi_voice)
    input_msg_queue = multiprocessing.Queue()
    speaking_queue = multiprocessing.Queue()
    start_bot(input_msg_queue, speaking_queue, discord_dabi)

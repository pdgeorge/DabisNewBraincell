import os
import asyncio
import tempfile
import concurrent.futures                         # NEW
import discord  # Pycord 2.5+, `py-cord[voice]`
from discord.ext import commands
import whisper
from pydub import AudioSegment
from dotenv import load_dotenv
from dabi_logging import dabi_print

load_dotenv()
DISCORD_TOKEN = os.getenv("CYRA_DISCORD")

WHISPER_MODEL = whisper.load_model("base")

# --------- NEW: a small thread‑pool just for Whisper ----------
whisper_pool = concurrent.futures.ThreadPoolExecutor(
    max_workers=2, thread_name_prefix="whisper"
)
# --------------------------------------------------------------

DEFAULT_RECORD = 10
PRIVILEGED_ROLES = {"TheGuyInChargeIGuess", "Cyra-chatter"}

# ----------  Discord client  ---------------
intents = discord.Intents.all()
intents.message_content = True
intents.voice_states = True

bot = discord.Bot(intents=intents)

# Helpers -------------------------------------------------

def audio_length(path: str) -> float:
    """Return duration of an audio file (seconds) with pydub."""
    return len(AudioSegment.from_file(path)) / 1000.0

# ---------- NEW helper that will run inside the pool ----------
def _transcribe_file(path: str) -> str:
    """Blocking call: Whisper STT + delete tmp file. Runs in thread."""
    try:
        text = WHISPER_MODEL.transcribe(path)["text"].strip()
    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
    return text
# ---------------------------------------------------------------

async def do_transcribe(ctx: discord.ApplicationContext, seconds: int):
    if not ctx.author.voice:
        return await ctx.respond(
            "❌ You must be in a voice channel.", ephemeral=True
        )

    voice_channel = ctx.author.voice.channel

    # Connect or move to author’s channel
    if ctx.guild.voice_client:
        vc: discord.VoiceClient = ctx.guild.voice_client
        if vc.channel != voice_channel:
            await vc.move_to(voice_channel)
    else:
        vc: discord.VoiceClient = await voice_channel.connect()

    sink = discord.sinks.WaveSink()

    async def on_finish(sink: discord.sinks.Sink, *_) -> None:
        loop = asyncio.get_running_loop()

        # ------- launch Whisper jobs in the pool -------------
        jobs, user_ids = [], []
        for uid, audio in sink.audio_data.items():
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            audio.file.seek(0)
            tmp.write(audio.file.read())
            tmp.close()
            user_ids.append(uid)
            # schedule blocking STT off‑thread
            jobs.append(loop.run_in_executor(whisper_pool, _transcribe_file, tmp.name))

        texts = await asyncio.gather(*jobs)  # parallel decode
        # ------------------------------------------------------

        # Merge usernames + texts and push to your queue
        formatted_msgs, msg_usernames, msg_msgs = [], [], []
        for uid, text in zip(user_ids, texts):
            user = await bot.fetch_user(uid)
            msg_usernames.append(user.display_name)
            msg_msgs.append(text or "...silence")
            formatted_msgs.append(f"{user.display_name}: {text or '...silence'}")

        formatted_return = {
            "msg_user": " ".join(msg_usernames) or "*No speech detected*",
            "msg_server": 1337,
            "msg_msg": " ".join(msg_msgs) or "*No speech detected*",
            "formatted_msg": " ".join(formatted_msgs) or "*No speech detected*",
        }
        print(formatted_return)
        global_input_msg_queue.put(formatted_return)

    vc.start_recording(sink, on_finish)
    await asyncio.sleep(seconds)
    vc.stop_recording()  # triggers on_finish

# ----------------------------------------------------------------
#                      YOUR COMMANDS (unchanged
#            except where noted: /transcribe returns early)
# ----------------------------------------------------------------
connections = {}
global_input_msg_queue = None
global_speaking_queue = None
listening_flag = False

@bot.event
async def on_ready():
    dabi_print(f"{bot.user} is ready and online!")
    await bot.sync_commands()
    dabi_print("Slash commands synced.")

@bot.event
async def on_message(message: discord.message):
    if message.author.bot:
        return
    if message.channel.name == "dabi-talks":
        await message.channel.send("hello")

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

@bot.slash_command(name="listen", description="Play back items from the speaking queue")
@commands.has_any_role(*PRIVILEGED_ROLES)
async def listen(ctx: discord.ApplicationContext):
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
                to_play = global_speaking_queue.get()
                vc.stop()
                vc.play(discord.FFmpegPCMAudio(to_play))
                delay = audio_length(to_play) + 0.5
                dabi_print(f"Playing {to_play} ({delay:.1f}s)")
                await asyncio.sleep(delay)
                try:
                    os.remove(to_play)
                except OSError:
                    pass
            if listening_flag:
                await do_transcribe(ctx=ctx, seconds=DEFAULT_RECORD)
                await asyncio.sleep(0.1)
            await asyncio.sleep(0.1)
    except Exception as e:
        dabi_print(f"Error in listen loop: {e}")

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

@bot.slash_command(name="transcribe", description="Record and transcribe this voice channel")
@commands.has_any_role(*PRIVILEGED_ROLES)
async def transcribe(
    ctx: discord.ApplicationContext,
    seconds: discord.Option(int, "Seconds to record (1‑120)",
                            default=DEFAULT_RECORD, min_value=1, max_value=120)  # type: ignore
):
    # ---------- NEW: run recorder in background so user gets instant reply
    asyncio.create_task(do_transcribe(ctx=ctx, seconds=seconds))
    await ctx.respond(f"🎙️ Recording for {seconds}s …", ephemeral=True)

# --------------------------------------------------------
#  ENTRY‑POINT  (unchanged)
# --------------------------------------------------------
def start_bot(input_msg_queue, speaking_queue):
    global global_input_msg_queue, global_speaking_queue
    global_input_msg_queue = input_msg_queue
    global_speaking_queue = speaking_queue
    try:
        bot.run(DISCORD_TOKEN)
    finally:
        whisper_pool.shutdown(wait=True)          # NEW – clean exit

if __name__ == "__main__":
    import multiprocessing
    input_msg_queue = multiprocessing.Queue()
    speaking_queue = multiprocessing.Queue()
    start_bot(input_msg_queue, speaking_queue)
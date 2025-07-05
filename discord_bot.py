import os
import asyncio
import tempfile

import discord                 # Pycord 2.5+, `py-cord[voice]`
import whisper
from pydub import AudioSegment
from dotenv import load_dotenv
from dabi_logging import dabi_print

load_dotenv()
DISCORD_TOKEN = os.getenv("CYRA_DISCORD")

WHISPER_MODEL = whisper.load_model("base") 
DEFAULT_RECORD = 10

# ----------  Discord client  ---------------
intents = discord.Intents.all()
intents.message_content = True
intents.voice_states = True

bot = discord.Bot(intents=intents)

# Helpers -------------------------------------------------
def audio_length(path: str) -> float:
    """Return duration of an audio file (seconds) with pydub."""
    return len(AudioSegment.from_file(path)) / 1000.0

connections = {}
global_input_msg_queue = None
global_speaking_queue = None
global_communicating = False

# --------------------------------------------------------
#  EVENTS
# --------------------------------------------------------
@bot.event
async def on_ready():
    dabi_print(f"{bot.user} is ready and online!")
    await bot.sync_commands()
    dabi_print("Slash commands synced.")

# --------------------------------------------------------
#  SIMPLE COMMANDS
# --------------------------------------------------------
@bot.slash_command(name="hello", description="Say hello to the bot!")
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

# --------------------------------------------------------
#  LISTEN command – plays audio files from speaking_queue
# --------------------------------------------------------
@bot.slash_command(name="listen", description="Play back items from the speaking queue")
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
            await asyncio.sleep(0.1)
    except Exception as e:
        dabi_print(f"Error in listen loop: {e}")

# --------------------------------------------------------
#  /TRANSCRIBE  – join, record N seconds, Whisper transcribe
# --------------------------------------------------------
@bot.slash_command(name="transcribe", description="Record and transcribe this voice channel")
async def transcribe(
    ctx: discord.ApplicationContext,
    seconds: discord.Option(int, "Seconds to record (1‑120)", default=DEFAULT_RECORD, min_value=1, max_value=120) # type: ignore
):
    if not ctx.author.voice:
        return await ctx.respond("❌ You must be in a voice channel.", ephemeral=True)

    voice_channel = ctx.author.voice.channel
    await ctx.respond(f"🎙️ Recording for **{seconds} s** …")

    # Connect or move to author’s channel
    vc: discord.VoiceClient
    if ctx.guild.voice_client:
        vc = ctx.guild.voice_client
        if vc.channel != voice_channel:
            await vc.move_to(voice_channel)
    else:
        vc = await voice_channel.connect()

    sink = discord.sinks.WaveSink()        # separate WAV per speaker

    async def on_finish(sink: discord.sinks.Sink, *args):
        lines = []
        for uid, audio in sink.audio_data.items():
            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
                audio.file.seek(0)
                tmp.write(audio.file.read())
                wav_path = tmp.name

            text = WHISPER_MODEL.transcribe(wav_path)["text"].strip()
            os.unlink(wav_path)
            user = await bot.fetch_user(uid)
            lines.append(f"**{user.display_name}**: {text or '*…silence*'}")

        msg = "📝 **Transcript**\n" + ("\n".join(lines) if lines else "*No speech detected*")
        await ctx.send(msg)

        await vc.disconnect(force=True)     # leave voice

    vc.start_recording(sink, on_finish)
    await asyncio.sleep(seconds)
    vc.stop_recording()                     # triggers on_finish

# --------------------------------------------------------
#  ENTRY‑POINT  (keeps your start_bot signature unchanged)
# --------------------------------------------------------
def start_bot(input_msg_queue, speaking_queue):
    global global_input_msg_queue, global_speaking_queue
    global_input_msg_queue = input_msg_queue
    global_speaking_queue = speaking_queue
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    # quick local test run
    import multiprocessing
    input_msg_queue = multiprocessing.Queue()
    speaking_queue = multiprocessing.Queue()
    start_bot(input_msg_queue, speaking_queue)
from dotenv import load_dotenv
import asyncio
import random
import os
import websockets
import re
import json
import twitchio
import twitchio.ext.pubsub
from twitchio.ext import pubsub

load_dotenv()
        
client = twitchio.Client(token=os.getenv("ACCESS_TOKEN"))
client.pubsub = pubsub.PubSubPool(client)

load_dotenv()
oauth = os.getenv("ACCESS_TOKEN")
irc_nick = os.getenv("BOT_NICK")
channel = os.getenv("CHANNEL")

pubsub_twitch_queue = None

PATTERN = r"@(.*?) :.*?.tmi.twitch.tv PRIVMSG #(.*?) :(.*)"
REGEX_PATTERN = re.compile(PATTERN)
        
##########################################################
### The below is related to pubsub events              ###
### Channel Points, follows, subscriptions, etc.       ###
### Things that cannot be handled by WebSocket comms   ###
##########################################################

@client.event()
async def event_pubsub_channel_points(event: pubsub.PubSubChannelPointsMessage):
    to_send = await extract_chan_point_info(event._data)
    print(event.reward.title)
    if to_send != None:
        pubsub_twitch_queue.put(json.dumps(to_send))
        
@client.event()
async def event_pubsub_bits(event: pubsub.PubSubBitsMessage):
    print(f"Received {event.bits_used} with a message {event.message} from {event.user} in channel {event.channel_id}")
    
# Subscriber things don't work "yet"
# @client.event()
# async def event_pubsub_channel_subscriptions(event: pubsub.PubSubChannelSubscribe):
#     print("subscription?!")
#     print(f"{event}")
#     print(f"{event.channel=} and {event.context=} and {event.cumulative_months=} and {event.emotes=} and {event.is_gift=} and {event.message=} and {event.multi_month_duration=} and {event.recipient=} and {event.streak_months=} and {event.sub_plan=} and {event.sub_plan_name} and {event.time} and {event.topic} and {event.user}")

# For extracting information required, only will work for specified channel point redemptions
# When adding a new channel point redemption, add a channel point redeem, make sure it allows text inputs
# Make note of the name that it uses.
async def extract_chan_point_info(pubsub_msg):
    formatted_msg = None
    formatted_return = None
    
    chosen_redemptions = ["Ask Dabi A Q"]
    for redeem in chosen_redemptions:
        if redeem == pubsub_msg["message"]["data"]["redemption"]["reward"]["title"]:
            msg_username = pubsub_msg["message"]["data"]["redemption"]["user"]["display_name"]
            msg_server = str(pubsub_msg["message"]["data"]["redemption"]["channel_id"])
            msg_msg = pubsub_msg["message"]["data"]["redemption"]["user_input"]
            formatted_msg = f"twitch:{msg_username}: {msg_msg}"
            
            formatted_return = {
                "msg_user": msg_username,
                "msg_server": msg_server,
                "msg_msg": msg_msg,
                "formatted_msg": formatted_msg
            }
            
    return formatted_return
            
    
# For when Dabi is in assist mode
async def assist():
    topics = [
        twitchio.ext.pubsub.channel_points(os.getenv("ACCESS_TOKEN"))[int(os.getenv("CHANNEL_ID"))],
        twitchio.ext.pubsub.bits(os.getenv("ACCESS_TOKEN"))[int(os.getenv("CHANNEL_ID"))]        
        ]
    await client.pubsub.subscribe_topics(topics)
    await client.start()
    
##########################################################
### The below are all related to Twitch Chat Messaging ###
### Reading from Twitch Chat. Formatting. etc.         ###
##########################################################

async def convert_to_ping(twitch_msg):
    words = len(twitch_msg['message'].split())
    print(f"{words=}")
    if twitch_msg["message"][0] == "!":
        print(twitch_msg["message"])
        # Only pdgeorge can mindwipe the Dab.
        if twitch_msg["message"].find("reset") > -1 and twitch_msg["user_id"] == "54654420":
            twitch_msg["message"] = '𝓻𝓮𝓼𝓮𝓽'
        # Only pdgeorge can mindwipe the Dab.
        if twitch_msg["message"].find("change") > -1 and twitch_msg["user_id"] == "54654420":
            twitch_msg["message"] = twitch_msg["message"].replace("change", "𝓬𝓱𝓪𝓷𝓰𝓮")
            print(twitch_msg["message"])
    
    elif twitch_msg["message"].find("🤖") > -1 or twitch_msg["user_id"].find("100135110") > -1 or twitch_msg["message"][0] == "," or twitch_msg["message"][0] == "@" or twitch_msg["message"].find("𝓻𝓮𝓼𝓮𝓽") > -1 or twitch_msg["message"].find("𝓬𝓱𝓪𝓷𝓰𝓮") > -1 or words == 1:
        twitch_msg["message"] = 'PING'
        print("Found a bot message!")
        
    return twitch_msg

async def format_twitch_msg(twitch_msg):
    formatted_msg = None
    
    if twitch_msg["message"].find("PING") < 0:
        msg_username = twitch_msg["display_name"]
        msg_server = twitch_msg["channel"]
        msg_msg = twitch_msg["message"]
        formatted_msg = f"twitch:{msg_username}:{msg_msg}"
        
        formatted_return = {
            "msg_user": msg_username,
            "msg_server": msg_server,
            "msg_msg": msg_msg,
            "formatted_msg": formatted_msg
        }
        
        return formatted_return

async def on_twitch_message(twitch_ws, message, twitch_queue):
    print(message)
    # Highest priority, PING/PONG should occur before anything else.
    if "PING" in message:
        print(message)
        await twitch_ws.send("PONG :tmi.twitch.tv")

    if "PRIVMSG" in message:
        message_data = {}
        match = REGEX_PATTERN.search(message)
        groups = match.groups()
        key_value_pairs = groups[0].split(";")
        for pair in key_value_pairs:
            key, value = pair.split("=", 1)
            message_data[key.replace("-", "_")] = value
        message_data["channel"] = groups[1]
        message_data["message"] = groups[2].rstrip("\r\n")
            
        message_data = await convert_to_ping(message_data)
        message_data = await format_twitch_msg(message_data)
        print(f"{message_data=}")
        
        await forward_message(message_data, twitch_queue)
        
async def handle_twitch_messages(twitch_ws, twitch_queue):
    async for message in twitch_ws:
        await on_twitch_message(twitch_ws, message, twitch_queue)

##########################################################
### The below are related to everything Comms          ###
### Connecting, Handling, Forwarding messages to Queue ###
##########################################################

async def on_error(ws, error):
    print(error)
    
async def on_close(ws, close_status_code, close_msg):
    print("### closed connection ###")
    
async def on_open(ws):
    print("### opened connection ###")
    await ws.send("CAP REQ :twitch.tv/membership twitch.tv/tags twitch.tv/commands")
    await ws.send("PASS oauth:" + os.getenv("ACCESS_TOKEN"))
    await ws.send("NICK " + os.getenv("BOT_NICK"))
    await ws.send("JOIN #" + os.getenv("CHANNEL"))
    print("### connected to Twitch IRC API ###")

async def forward_message(message_data, twitch_queue):
    to_send = message_data
    if to_send:
        print(f"Queueing message: {to_send=}")
        twitch_queue.put(json.dumps(to_send))
    await asyncio.sleep(1)

async def handler(twitch_queue):
    # Make connection to Twitch
    async with websockets.connect("wss://irc-ws.chat.twitch.tv:443") as twitch_ws:
        await on_open(twitch_ws)
        twitch_task = asyncio.create_task(handle_twitch_messages(twitch_ws, twitch_queue))
        
        await twitch_task
            
def start_bot(mode, twitch_queue):
    global pubsub_twitch_queue
    print(mode)
    if mode == "chat":
        asyncio.run(handler(twitch_queue))
    elif mode == "assist":
        pubsub_twitch_queue = twitch_queue
        print("Ready to assist!")
        client.loop.run_until_complete(assist())
            
if __name__ == "__main__":
    print("lol main")
    import multiprocessing
    twitch_queue = multiprocessing.Queue()
    start_bot("chat", twitch_queue)
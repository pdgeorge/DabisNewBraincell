import asyncio
import json
import os
import requests
import websockets
from twitch_wrappers import TW
from dotenv import load_dotenv
from dabi_logging import dabi_print
from datetime import datetime

from event_bus import EventBus

load_dotenv()

_event_bus = EventBus()

followers = None
global_input_msg_queue = None
global_chat_mode = False
tw = TW()
first_now = datetime.now()
first_unix_timestamp_float = first_now.timestamp()
last_msg_time = int(first_unix_timestamp_float)
chat_messages = []

time_to_read_chat = 60

# ACCESS_TOKEN = os.getenv('DABI_ACCESS_TOKEN')   # Generated from your authentication mechanism, make sure it is scoped properly
CHANNEL_ID = os.getenv('PDGEORGE_CHANNEL_ID')   # The channel ID of the channel you want to join
CLIENT_ID = os.getenv('DABI_CLIENT_ID')         # The same Client ID used to generate the access token

async def _ensure_bus():
    print("ensuring_bus")
    await _event_bus.connect()

async def _startup():
    try:
        await _ensure_bus()
    except Exception as e:
        print("[twitch_events] RabbitMQ connect failed (continuing with Queues):", e)

async def publish_event(key, in_data):
    await _event_bus.publish(
        routing_key = key,      # label used by consumers
        type_ = "reward.redeemed.v1",     # event type
        data = in_data,
        source = "dabi.twitch_events"     # who produced this event
    )

async def collect_messages(message):
    if message.get("msg_msg", "")[0] == "!":
        return None
    global last_msg_time
    global chat_messages
    global time_to_read_chat
    now = datetime.now()
    unix_timestamp_float = now.timestamp()
    this_msg_time = int(unix_timestamp_float)
    chat_messages.append(message)
    if (len(chat_messages) >= 10) or ((this_msg_time - last_msg_time) > time_to_read_chat):
        msg_usernames   = []
        formatted_msgs  = []
        msg_msgs        = []
        for cm in chat_messages:
            msg_usernames.append(cm.get("msg_user", ""))
            formatted_msgs.append(cm.get("formatted_msg", ""))
            msg_msgs.append(cm.get("msg_msg", ""))
        formatted_return = {
            "msg_user": (" ".join(msg_usernames) if msg_usernames else ""),
            "msg_server": "pdgeorge",
            "msg_msg": (" ".join(msg_msgs) if msg_msgs else ""),
            "formatted_msg": (" ".join(formatted_msgs) if formatted_msgs else "")
        }
        now = datetime.now()
        unix_timestamp_float = now.timestamp()
        last_msg_time = int(unix_timestamp_float)
        chat_messages = []
        return formatted_return
    else:
        return None

async def handle_twitch_msg(event):
    global global_input_msg_queue
    to_send = await extract_message_to_send_chat(event)
    to_send = await collect_messages(to_send)
    if to_send is not None:
        global_input_msg_queue.put(json.dumps(to_send))
        key = "twitch.msg"
        await publish_event(key, to_send)

async def extract_message_to_send_chat(event):
    formatted_msg = None
    formatted_return = None

    msg_username = event.get('payload', {}).get('event', {}).get('chatter_user_login', {})
    msg_msg = event.get('payload', {}).get('event', {}).get('message', {}).get('text', {})
    msg_server = event.get('payload', {}).get('event', {}).get('broadcaster_user_login', {})
    formatted_msg = f"twitch:{msg_username}: {msg_msg}"

    formatted_return = {
        "msg_user": msg_username,
        "msg_server": msg_server,
        "msg_msg": msg_msg,
        "formatted_msg": formatted_msg
    }
    
    return formatted_return

async def handle_follow(event):
    followers.append(event.get('payload', {}).get('event', {}).get('user_login', {}))
    follow_to_send = {
        "msg_user": event.get('payload', {}).get('event', {}).get('user_login', {}),
        "msg_server": event.get('payload', {}).get('event', {}).get('broadcaster_user_login', {}),
        "msg_msg": "Has just followed!",
        "formatted_msg": f"twitch:{event.get('payload', {}).get('event', {}).get('user_login', {})}: Has just followed!"
    }
    global_input_msg_queue.put(json.dumps(follow_to_send))
    dabi_print(json.dumps(follow_to_send))
    key = "twitch.follow"
    await publish_event(key, follow_to_send)

async def handle_sub(event):
    global global_input_msg_queue

    to_send = await extract_message_to_sub(event)
    global_input_msg_queue.put(json.dumps(to_send))
    key = "twitch.sub"
    await publish_event(key, to_send)

async def extract_message_to_sub(event):
    formatted_msg = None
    formatted_return = None

    msg_username = event.get('payload', {}).get('event', {}).get('user_login', {})
    msg_msg = "Has just subscribbed because they are a WIDEGIGACHAD"
    msg_server = event.get('payload', {}).get('event', {}).get('broadcaster_user_login', {})
    formatted_msg = f"twitch:{msg_username}: {msg_msg}"

    formatted_return = {
                "msg_user": msg_username,
                "msg_server": msg_server,
                "msg_msg": msg_msg,
                "formatted_msg": formatted_msg
            }
    
    return formatted_return

# Can do more with bits than just "Here is the message that came with the bits". This is just the start
async def handle_bits(event):
    formatted_msg = None
    formatted_return = None

    # bits_spent = event.get('payload', {}).get('event', {}).get('bits', {}) # Don't want to add this in yet
    # bits_type = event.get('payload', {}).get('event', {}).get('type', {}) # Not needed yet? "cheer", "power_up", "combo"
    # cheer = message in chat
    # power_up = "BIG EMOTE" etc.
    # combo = click the heart

    msg_username = event.get('payload', {}).get('event', {}).get('user_login', {})
    msg_msg = event.get('payload', {}).get('event', {}).get('message', {}).get('text', {})
    msg_server = event.get('payload', {}).get('event', {}).get('broadcaster_user_login', {})
    formatted_msg = f"twitch:{msg_username}: {msg_msg}"

    formatted_return = {
                "msg_user": msg_username,
                "msg_server": msg_server,
                "msg_msg": msg_msg,
                "formatted_msg": formatted_msg
            }
    
    global_input_msg_queue.put(json.dumps(formatted_return))
    key = "twitch.bits"
    await publish_event(key, formatted_return)

async def handle_raid(event):
    formatted_msg = None
    formatted_return = None

    # raided_viewers = event.get('payload', {}).get('event', {}).get('viewers', {}) # NOT NEEDED
    msg_username = event.get('payload', {}).get('event', {}).get('from_broadcaster_user_login', {})
    msg_msg = f"{msg_username} has just raided us! Show them some love! Give them an introduction in to who you are, tell them what we have been doing!"
    msg_server = event.get('payload', {}).get('event', {}).get('broadcaster_user_login', {})
    formatted_msg = f"twitch:{msg_username}: {msg_msg}"

    formatted_return = {
                "msg_user": msg_username,
                "msg_server": msg_server,
                "msg_msg": msg_msg,
                "formatted_msg": formatted_msg
            }
    
    global_input_msg_queue.put(json.dumps(formatted_return))
    key = "twitch.raid"
    await publish_event(key, formatted_return)

async def handle_redemptions(event):
    global global_input_msg_queue
    global global_chat_mode
    event_title = event.get('payload', {}).get('event', {}).get('reward', {}).get('title', {})
    match event_title:
        case "Ask Dabi A Q":
            to_send = await extract_message_to_send_points(event)
            dabi_print(f"{to_send=}")
            global_input_msg_queue.put(json.dumps(to_send))
            key = "twitch.talk"
            await publish_event(key, to_send)
        case "InspireMe":
            formatted_received = await extract_message_to_send_points(event)
            dabi_print(formatted_received)
            temp_send = f"Inspire {formatted_received.get('msg_username', '')} Dabi! On the topic of {formatted_received.get('msg_msg', '')}"
            formatted_received["formatted_msg"] = f"twitch:{formatted_received.get('msg_username', '')}: {temp_send}"
            global_input_msg_queue.put(json.dumps(formatted_received))
            key = "twitch.inspire"
            await publish_event(key, formatted_received)
        case "brb":
            if global_chat_mode:
                global_chat_mode = False
                brb_msg = {
                    "msg_user": "pdgeorge",
                    "msg_server": "pdgeorge",
                    "msg_msg": "Ok, I'm back. Thanks for looking after chat.",
                    "formatted_msg": "twitch:pdgeorge: Ok, I'm back. Thanks for looking after chat."
                }
                global_input_msg_queue.put(json.dumps(brb_msg))
                key = "twitch.brb"
                await publish_event(key, brb_msg)
            else:
                global_chat_mode = True
                brb_msg = {
                    "msg_user": "pdgeorge",
                    "msg_server": "pdgeorge",
                    "msg_msg": "Can you look after chat while I'm away? Thanks bro.",
                    "formatted_msg": "twitch:pdgeorge: Can you look after chat while I'm away? Thanks bro."
                }
                global_input_msg_queue.put(json.dumps(brb_msg))
                key = "twitch.brb"
                await publish_event(key, brb_msg)
        case "general_test":
            await general_test(event)

async def general_test(event):
    print("general_test")
    print(f"{event=}")
    await _ensure_bus()
    publish_data={
        "reward_title": event.get('payload', {}).get('event', {}).get('reward', {}).get('title', {}),
        "reward_id": event.get('payload', {}).get('event', {}).get('reward', {}).get('id', {'ID_FAILED'}),
        "user": event.get('payload', {}).get('event', {}).get('user_name', {}),
        "cost": event.get('payload', {}).get('event', {}).get('reward', {}).get('cost', {'COST'})
    }
    key = "redeem.test"
    await publish_event(key, publish_data)

async def timeout_user(msg):
    formatted_return = None
    input_str = msg.get('msg_msg', {})
    online_chatters = tw.get_users_formatted()

    matched_name = next(
        (name for name in online_chatters if name.lower() in input_str.lower()),
        None
    )
    
    return formatted_return

async def extract_message_to_send_points(event):
    formatted_msg = None
    formatted_return = None

    msg_username = event.get('payload', {}).get('event', {}).get('user_name', {})
    msg_msg = event.get('payload', {}).get('event', {}).get('user_input', {})
    msg_server = event.get('payload', {}).get('event', {}).get('broadcaster_user_login', {})
    formatted_msg = f"twitch:{msg_username}: {msg_msg}"

    formatted_return = {
                "msg_user": msg_username,
                "msg_server": msg_server,
                "msg_msg": msg_msg,
                "formatted_msg": formatted_msg
            }

    return formatted_return

async def on_message(ws, message):
    global followers
    global global_input_msg_queue
    global global_chat_mode
    event = json.loads(message)
    if event['metadata']['message_type'] == 'session_welcome':
        session_id = event['payload']['session']['id']
        dabi_print(f'{session_id=}')
        subscribe_array = [
            {
            'type': 'channel.follow',
            'version': '2',
            'condition': {
                'broadcaster_user_id': CHANNEL_ID,
                'moderator_user_id': CHANNEL_ID
            },
            'transport': {
                'method': 'websocket',
                'session_id': f'{session_id}',
            }
            },{
                'type': 'channel.channel_points_custom_reward_redemption.add',
                'version': '1',
                'condition': {
                    "broadcaster_user_id": CHANNEL_ID
                },
                'transport': {
                    'method': 'websocket',
                    'session_id': f'{session_id}',
                }
            },{
                'type': 'channel.subscribe',
                'version': '1',
                'condition': {
                    "broadcaster_user_id": CHANNEL_ID
                },
                'transport': {
                    'method': 'websocket',
                    'session_id': f'{session_id}',
                }
            },{
                'type': 'channel.bits.use',
                'version': '1',
                'condition': {
                    "broadcaster_user_id": CHANNEL_ID
                },
                'transport': {
                    'method': 'websocket',
                    'session_id': f'{session_id}',
                }
            },{
                'type': 'channel.raid',
                'version': '1',
                'condition': {
                    "to_broadcaster_user_id": CHANNEL_ID
                },
                'transport': {
                    'method': 'websocket',
                    'session_id': f'{session_id}',
                }
            },{
                'type': 'channel.chat.message',
                'version': '1',
                'condition': {
                    "broadcaster_user_id": CHANNEL_ID,
                    'user_id': CHANNEL_ID
                },
                'transport': {
                    'method': 'websocket',
                    'session_id': f'{session_id}',
                }
            }
        ]
        for subscribe in subscribe_array:
            dabi_print(subscribe)
            response = requests.post(
                'https://api.twitch.tv/helix/eventsub/subscriptions',
                headers={
                    'Authorization': f'Bearer {tw.access_token}',
                    'Client-Id': CLIENT_ID,
                    'Content-Type': 'application/json',
                    'Accept': 'application/vnd.twitchtv.v5+json',
                },
                data=json.dumps(subscribe)
            )
            dabi_print(f'{response.content=}')
    
    elif event.get('metadata', {}).get('message_type', {}) == 'session_keepalive':
        pass
    elif event.get('metadata', {}).get('message_type', {}) == 'notification' and event.get('metadata', {}).get('subscription_type', {}) == 'channel.follow':
        # print(f'[🔔] Event:\n{event}')
        if event.get('payload', {}).get('event', {}).get('user_login', {}) not in followers:
            await handle_follow(event)
    elif event.get('metadata', {}).get('message_type', {}) == 'notification' and event.get('metadata', {}).get('subscription_type', {}) == 'channel.channel_points_custom_reward_redemption.add':
        dabi_print(event)
        await handle_redemptions(event)
    elif event.get('metadata', {}).get('message_type', {}) == 'notification' and event.get('metadata', {}).get('subscription_type', {}) == 'channel.chat.message' and event.get('payload', {}).get('event', {}).get('channel_points_custom_reward_id', {}) == None:
        if global_chat_mode:
            await handle_twitch_msg(event)
    elif event.get('metadata', {}).get('message_type', {}) == 'notification' and event.get('metadata', {}).get('subscription_type', {}) == 'channel.subscribe':
        dabi_print(event)
        await handle_sub(event)
    elif event.get('metadata', {}).get('message_type', {}) == 'notification' and event.get('metadata', {}).get('subscription_type', {}) == 'channel.bits.use':
        dabi_print(event)
        await handle_bits(event)
    elif event.get('metadata', {}).get('message_type', {}) == 'notification' and event.get('metadata', {}).get('subscription_type', {}) == 'channel.raid':
        dabi_print(event)
        await handle_raid(event)
    else:
        dabi_print(event)

async def ws_conn():
    url = 'wss://eventsub.wss.twitch.tv/ws'
    async with websockets.connect(url) as ws:
        dabi_print('[ℹ️] Connected to WebSocket')
        try:
            while True:
                message = await ws.recv()
                await on_message(ws, message)
        except websockets.ConnectionClosed as e:
            dabi_print(f'[❗] WebSocket closed: {e}')
        finally:
            dabi_print('[ℹ️] Closing WebSocket connection...')

async def grab_followers():
    all_followers = []
    cursor = None

    headers = {
        'Client-ID': CLIENT_ID,
        'Authorization': f'Bearer {tw.access_token}',
    }
    
    url = f'https://api.twitch.tv/helix/channels/followers?broadcaster_id={CHANNEL_ID}'

    while True:
        params = {'after': cursor} if cursor else {}
        response = requests.get(url, headers=headers, params=params)
        data = response.json()

        # Collect user_login from the current page
        try:
            all_followers.extend([follower['user_login'] for follower in data['data']])
        except Exception as e:
            dabi_print(f"{data=}\n", repr(e))


        cursor = data.get('pagination', {}).get('cursor', {})

        if not cursor:
            dabi_print(f"{data.get('total', {})=}")
            break

    return all_followers

async def main():
    global followers
    # run here once
    await _startup()
    followers = await grab_followers()

    await asyncio.gather(ws_conn())

def start_events(input_msg_queue, dabi_print, chat_mode):
    global global_input_msg_queue
    global global_chat_mode
    global_chat_mode = chat_mode
    global_input_msg_queue = input_msg_queue
    dabi_print("TwitchEvent process has started")
    tw.update_key()
    tw.validate()
    asyncio.run(main())

async def test_main():
    import multiprocessing
    global global_input_msg_queue
    global global_chat_mode
    global_chat_mode = False
    global_input_msg_queue = multiprocessing.Queue()
    dabi_print("Running the test version")
    validate_response = tw.validate()
    dabi_print(validate_response)
    await main()

if __name__ == "__main__":
    try:
        asyncio.run(test_main())
    except KeyboardInterrupt:
        dabi_print('[❗] Application interrupted. Shutting down...')
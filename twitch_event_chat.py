import json
import os
import requests
import rel
import websocket
from dotenv import load_dotenv

load_dotenv()

ACCESS_TOKEN = os.getenv('ACCESS_TOKEN') # Generated from your authentication mechanism, make sure it is scoped properly
CHANNEL_ID = os.getenv('CHANNEL_ID')     # The channel ID of the channel you want to join
CLIENT_ID = os.getenv('CLIENT_ID')       # The same Client ID used to generate the access token


session_id = None

def on_message(ws, message):
    event = json.loads(message)
    print(event)
    if event.get('metadata', {}).get('message_type') == 'session_welcome':
        ####
        # Store the Session ID to use with event subscription
        session_id = event.get('payload', {}).get('session', {}).get('id')
        print(f'{session_id=}')
        ####
        # Fill in this dict based on the event you want to subscribe to
        # https://dev.twitch.tv/docs/eventsub/eventsub-subscription-types/#userupdate
        subscribe = {
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
        ####
        # Send a POST to subscribe to the event
        response = requests.post(
            'https://api.twitch.tv/helix/eventsub/subscriptions',
            headers={
                'Authorization': f'Bearer {ACCESS_TOKEN}', 
                'Client-Id': CLIENT_ID, 
                'Content-Type': 'application/json',
                'Accept': 'application/vnd.twitchtv.v5+json'
            },
            data=json.dumps(subscribe)
        )
        ####
        # Print event subscription response
        print(f'{response.content=}')

    # This is called whenever a message is received if the program is running.
    elif 'message' in event.get('payload', {}).get('event', {}): 
        print(f"====================================\n{event=}\n====================================")

def on_error(ws, error):
    print(f' [❗] Error: {error}')

def on_close(ws, close_status_code, close_msg):
    print(f' [❗] Closed WebSockets connection.\n\tCode: {close_status_code}\n\tMessage:{close_msg}')

def on_open(ws):
    print(' [ℹ️] Opened WebSockets connection')

def chat_websocket():
    try:
        websocket.enableTrace(False)
        ws = websocket.WebSocketApp('wss://eventsub.wss.twitch.tv/ws',
                                            on_message=on_message,
                                            on_open=on_open,
                                            on_error=on_error,
                                            on_close=on_close)
        ws.run_forever(dispatcher=rel, reconnect=5)
        print(f' [🏃] Running forever...')
        # Keyboard interrupt
        rel.signal(2, rel.abort)
        rel.dispatch()
    except Exception as exception:
        print(f' [‼️] Error: {exception}')
        exit(1)

chat_websocket()
import os
import requests
from dotenv import load_dotenv, set_key

load_dotenv()

CLIENT_ID = os.getenv('DABI_CLIENT_ID')
CLIENT_SECRET = os.getenv('DABI_CLIENT_SECRET')
REFRESH_TOKEN = os.getenv('DABI_REFRESH_TOKEN')
TOKEN_URL = "https://id.twitch.tv/oauth2/token"
ENV_FILE = ".env"
ACCESS_TOKEN = os.getenv('DABI_ACCESS_TOKEN')
CHANNEL_ID = os.getenv('PDGEORGE_CHANNEL_ID')
USER_ID = os.getenv('BOT_USER_ID')

class TW():
    def __init__(self):
        self.client_id = CLIENT_ID
        self.client_secret = CLIENT_SECRET
        self.refresh_token = REFRESH_TOKEN
        self.token_url = TOKEN_URL
        self.access_token = ACCESS_TOKEN
        self.channel_id = CHANNEL_ID
        self.user_id = USER_ID

    def get_users_formatted(self):
        response = self.get_users()
        response.get('data', {})

        user_names = [user['user_name'] for user in response['data']]

        return user_names

    def get_users(self):
        url = f'https://api.twitch.tv/helix/chat/chatters?broadcaster_id={CHANNEL_ID}&moderator_id={CHANNEL_ID}'

        headers = {
            'Authorization': f'Bearer {ACCESS_TOKEN}',
            'Client-Id': CLIENT_ID,
            'Content-Type': 'application/json'
        }

        response = requests.get(url, headers=headers)

        return response.json()

    def get_moderators_formatted(self):
        response = self.get_moderators()
        response.get('data',{})

        user_names = [user['user_name'].lower() for user in response['data']]

        return user_names

    def get_moderators(self):
        url = f'https://api.twitch.tv/helix/moderation/moderators?broadcaster_id={CHANNEL_ID}'

        headers = {
            'Authorization': f'Bearer {ACCESS_TOKEN}',
            'Client-Id': CLIENT_ID,
            'Content-Type': 'application/json'
        }

        response = requests.get(url, headers=headers)

        return response.json()

    def validate(self):
        load_dotenv(override=True)
        ACCESS_TOKEN = os.getenv('DABI_ACCESS_TOKEN')
        url = 'https://id.twitch.tv/oauth2/validate'

        headers = {
            'Authorization': f'OAuth {ACCESS_TOKEN}'
        }

        response = requests.get(url, headers=headers)
        
        return response.json()
        
    def get_user(self, user):
        url = f'https://api.twitch.tv/helix/users?login={user}'

        headers = {
            'Authorization': f'Bearer {ACCESS_TOKEN}',
            'Client-Id': CLIENT_ID,
            'Content-Type': 'application/json'
        }

        response = requests.get(url, headers=headers)
        
        return response.json()
        
    def get_user_id(self, user):
        url = f'https://api.twitch.tv/helix/users?login={user}'

        headers = {
            'Authorization': f'Bearer {ACCESS_TOKEN}',
            'Client-Id': CLIENT_ID,
            'Content-Type': 'application/json'
        }

        response = requests.get(url, headers=headers)
        data = response.json()

        return data.get('data', {})[0].get('id', {})
        
    def timeout_user(self, user_name: str, length: int):
        user_id = self.get_user_id(user_name)
        response = "Error"
        print(f"Get user_id = {user_id=}")

        # user_id = response.get('data', {})[0].get('id', {})

        url = f'https://api.twitch.tv/helix/moderation/bans?broadcaster_id={CHANNEL_ID}&moderator_id={CHANNEL_ID}'

        headers = {
            'Authorization': f'Bearer {ACCESS_TOKEN}',
            'Client-Id': CLIENT_ID,
            'Content-Type': 'application/json'
        }

        data = {
            "data":
            {
                "user_id": user_id,
                "duration": length,
                "reason": "test"
            }
        }

        response = requests.post(url, headers=headers, json=data)
        print(f"=tw.timeout_user====={data=}")
        print(f"=tw.timeout_user====={user_name=}")
        print(f"=tw.timeout_user====={response=}")
        print(f"=tw.timeout_user====={response.json()=}")
        return response.json()

    def send_msg(self, msg_to_send):
        url = f'https://api.twitch.tv/helix/chat/messages'

        headers = {
            'Authorization': f'Bearer {ACCESS_TOKEN}',
            'Client-Id': CLIENT_ID,
            'Content-Type': 'application/json'
        }

        data = {
            "broadcaster_id": CHANNEL_ID,
            "sender_id": CHANNEL_ID,
            "message": msg_to_send
        }

        response = requests.post(url, headers=headers, json=data)

        return response.json()

    def refresh_access_token(self, client_id, client_secret, refresh_token):
        try:
            # Parameters for the POST request
            params = {
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }

            # Make the POST request
            response = requests.post(TOKEN_URL, params=params)
            response_data = response.json()

            if response.status_code == 200:
                # Extract new tokens
                access_token = response_data["access_token"]
                refresh_token = response_data.get("refresh_token", refresh_token)

                # Return tokens for further use
                return access_token, refresh_token
            else:
                # Handle errors
                print("Error refreshing token:", response_data)
                return None, None

        except Exception as e:
            print("Exception occurred while refreshing token:", str(e))
            return None, None
        
    def update_access_token_in_env(self, access_token, env_file):
        try:
            set_key(env_file, "DABI_ACCESS_TOKEN", access_token)
        except Exception as e:
            print("Failed to update .env file:", str(e))

    def update_key(self):
        new_access_token, new_refresh_token = self.refresh_access_token(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN)
        if new_access_token:
            print("Token refresh successful!")
            self.update_access_token_in_env(new_access_token, ENV_FILE)
            self.validate()
            return new_access_token
        else:
            print("Token refresh failed.")

# A list of example usages and testing
if __name__ == "__main__":
    tw = TW() # 1 for first run, 0 for any subsequent running
    print("Moderators!")
    response = tw.get_moderators_formatted()
    print(response)
    print("End Moderators")
    response = tw.timeout_user("t_b0n3", 1)
    print(response)
    print("Formatted! Chatters!")
    response_two = tw.get_users_formatted()
    print(response_two)
    response = tw.send_msg("Hello, world!")
    print(response)
# else:
    # We want this to run when always
    # new_key = tw.update_key() # For updating the key
    # response = tw.validate()
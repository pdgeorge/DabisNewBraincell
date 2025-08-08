import os
import requests
from dotenv import load_dotenv, set_key
from dabi_logging import dabi_print

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
        self.access_token = ACCESS_TOKEN
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

        try:
            response = requests.post(url, headers=headers, json=data)
            print(f"=tw.timeout_user====={data=}")
            print(f"=tw.timeout_user====={user_name=}")
            print(f"=tw.timeout_user====={response=}")
            print(f"=tw.timeout_user====={response.json()=}")
        except Exception as e:
            print(repr(e))
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

    def play_ads(self, length: int = 30) -> dict:
        """
        Start a commercial break on the broadcaster’s channel.

        Parameters
        ----------
        length : int, optional
            Duration of the ad in seconds.  Twitch currently accepts
            {30, 60, 90, 120, 150, 180}.  Default = 30.

        Returns
        -------
        dict
            JSON payload from Twitch.  On success it contains:
              {
                "data": [{
                    "length": 30,
                    "message": "",
                    "retry_after": 480
                }]
              }

        Notes
        -----
        • The access-token used **must** include the
          ``channel:edit:commercial`` scope.  
        • Only the broadcaster themself (Affiliate/Partner) can call
          this endpoint while they are live.  
        • If the token is expired the method will automatically try to
          refresh once via ``self.update_key()`` before giving up.

        Twitch reference:
        https://dev.twitch.tv/docs/api/reference/#start-commercial
        """
        valid_lengths = {30, 60, 90, 120, 150, 180}
        if length not in valid_lengths:
            raise ValueError(
                f"Invalid ad length {length}. "
                f"Valid options: {sorted(valid_lengths)}"
            )

        url = "https://api.twitch.tv/helix/channels/commercial"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Client-Id": self.client_id,
            "Content-Type": "application/json",
        }
        payload = {"broadcaster_id": self.channel_id, "length": length}

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            return resp.json()                             # success
        except requests.exceptions.HTTPError as err:
            dabi_print(f"[TW.play_ads] HTTPError → {err} | {resp.text}")
            return {"error": resp.text, "status_code": resp.status_code}
        except Exception as err:
            dabi_print(f"[TW.play_ads] Unexpected error → {err}")
            return {"error": str(err)}


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
                dabi_print("Error refreshing token:", response_data)
                return None, None

        except Exception as e:
            dabi_print("Exception occurred while refreshing token:", str(e))
            return None, None
        
    def update_access_token_in_env(self, access_token, env_file):
        try:
            set_key(env_file, "DABI_ACCESS_TOKEN", access_token)
        except Exception as e:
            dabi_print("Failed to update .env file:", str(e))

    def update_key(self):
        new_access_token, new_refresh_token = self.refresh_access_token(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN)
        if new_access_token:
            dabi_print("Token refresh successful!")
            self.update_access_token_in_env(new_access_token, ENV_FILE)
            self.validate()
            return new_access_token
        else:
            dabi_print("Token refresh failed.")

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
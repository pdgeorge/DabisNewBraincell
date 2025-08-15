import os
import requests
from dotenv import load_dotenv
from flask import Flask, request, redirect

load_dotenv()

app = Flask(__name__)

CLIENT_ID = os.getenv('DABI_CLIENT_ID')
CLIENT_SECRET = os.getenv('DABI_CLIENT_SECRET')
REDIRECT_URI = 'http://localhost:5000/callback'
SCOPES = 'channel:bot moderator:manage:banned_users moderator:manage:chat_messages user:read:chat user:write:chat channel:manage:redemptions channel:read:charity moderator:read:followers channel:read:subscriptions'  # Add other scopes as needed

auth_url = f'https://id.twitch.tv/oauth2/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope={SCOPES}&state=xyz'

@app.route('/')
def index():
    return f'<a href="{auth_url}">Authorize with Twitch</a>'

@app.route('/callback')
def callback():
    code = request.args.get('code')
    state = request.args.get('state')

    if state != 'xyz':
        return "State does not match!", 400

    # Step 4: Exchange the authorization code for an access token
    token_url = 'https://id.twitch.tv/oauth2/token'
    token_data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': REDIRECT_URI
    }

    token_response = requests.post(token_url, data=token_data)
    token_json = token_response.json()

    access_token = token_json.get('access_token')
    refresh_token = token_json.get('refresh_token')

    return f'Access Token: {access_token}<br>Refresh Token: {refresh_token}'

if __name__ == '__main__':
    app.run(debug=True, port=5000)
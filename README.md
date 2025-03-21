# DabisNewBraincell

## What or who is Dabi?

Dabi is a streamer pet that can interact with Twitch chat, either through listening to Twitch Chat directly, through channel point redeems or by responding to when people follow or subscribe. Additionally, Dabi is able to talk directly with the streamer, or other collaborators, in Discord calls.

## Setting up Dabi

* Clone the repository

* Ensure Python is installed, preferably Python 3.12+

* `pip install -r requirements.txt`

* Create a .env file at the base directory (the same as main.py) and populate it as follows:

ACCESS_TOKEN=<replace with Twitch access token>
CHANNEL_ID=<The channel ID of the channel you want to join>
CLIENT_ID=<The same Client ID used to generate the access token>
OPENAI_API_KEY=<Your openAI API key>
CYRA_DISCORD=<Discord token>

Twitch tokens can be generated from https://twitchtokengenerator.com/
Discord tokens can be generated from https://discordapp.com/developers/applications/

Please remember that this is a personal project. There are elements which I would be far more scrutinous over in a professional capacity, however in a professional capacity I would not get to have such a cute derp.

Credits:
tbon_transcriber.py supplied by T-B0N3 with some modifications done by myself.

Linux upgrade:
sudo apt install build-essential
sudo apt install portaudio19-dev
pip install pyaudio

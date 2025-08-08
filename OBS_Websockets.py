import obswebsocket
from obswebsocket import obsws, requests
import math
import time
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

OBS_PASSWORD = os.getenv("OBS_PASSWORD")

class OBSWebsocketsManager():
    def __init__(self) -> None:
        self.ws = obsws("192.168.0.65", 4455, OBS_PASSWORD)
        self.ws.connect()
    
    def get_item_id(self, scene_name, element_name):
        response = self.ws.call(obswebsocket.requests.GetSceneItemList(sceneName=scene_name))
        
        items = response.getSceneItems()

        scene_item_id = None
        for item in items:
            if item['sourceName'] == element_name:
                scene_item_id = item['sceneItemId']
                break

        if scene_item_id:
            return scene_item_id
        else:
            return "F"

    def set_source_visibility(self, scene_name, element_name, set):

        scene_item_id = self.get_item_id(scene_name, element_name)

        transform_data = {
            "sceneName": scene_name,
            "sceneItemId": scene_item_id,
            "sceneItemEnabled": set
        }
        
        set_transform_request = obswebsocket.requests.SetSceneItemEnabled(**transform_data)
        self.ws.call(set_transform_request)

    def shake(self, scene_name, element_name, rot):
        scene_item_id = self.get_item_id(scene_name, element_name)

        transform_data = {
            "sceneName": scene_name,
            "sceneItemId": scene_item_id,
            "sceneItemTransform": {
                "rotation": rot
            }
        }

        set_transform_request = obswebsocket.requests.SetSceneItemTransform(**transform_data)
        self.ws.call(set_transform_request)

    async def move_up(self, scene_name, element_name):
        duration = 0.5
        start_y = 1080
        end_y = 580
        steps = 500
        delay = duration / steps
        id = self.get_item_id(scene_name, element_name)

        print("move_up")
        for step in range(1, steps + 1):
            t = step / steps
            current_y = int(start_y + (end_y - start_y) * t)
            print(f"{current_y}")
            self.ws.call(requests.SetSceneItemTransform(
                sceneName=scene_name,
                sceneItemId=id,
                sceneItemTransform={
                    "positionX": 0,
                    "positionY": current_y
                }))
            await asyncio.sleep(delay)

    async def move_down(self, scene_name, element_name):
        duration = 0.5
        start_y = 580
        end_y = 1080
        steps = 500
        delay = duration / steps
        id = self.get_item_id(scene_name, element_name)

        print("move_up")
        for step in range(1, steps + 1):
            t = step / steps
            current_y = int(start_y + (end_y - start_y) * t)
            print(f"{current_y}")
            self.ws.call(requests.SetSceneItemTransform(
                sceneName=scene_name,
                sceneItemId=id,
                sceneItemTransform={
                    "positionX": 0,
                    "positionY": current_y
                }))
            await asyncio.sleep(delay)

        print("move_down")
        for step in range(1, steps + 1):
            t = step / steps
            current_y = int(start_y + (end_y - start_y) * t)
            print(f"{current_y}")
            self.ws.call(requests.SetSceneItemPosition(
                item=element_name, 
                x=0, 
                y=current_y))
            await asyncio.sleep(delay)

    def source_checker(self, scene_name):
        response = self.ws.call(obswebsocket.requests.GetSceneItemList(sceneName=scene_name))
        print(f"{response=}")
        return response

    async def temp_display(self, element_name, input_time):
        response = self.ws.call(requests.GetCurrentProgramScene())
        current_scene_name = response.getSceneName()
        start_time = time.time()
        print("On")
        self.set_source_visibility(current_scene_name, element_name, True)
        await self.move_up(current_scene_name, element_name)
        while time.time() < (start_time + input_time):
            await asyncio.sleep(0.1)
        await self.move_down(current_scene_name, element_name)
        print("off")
        self.set_source_visibility(current_scene_name, element_name, False)
        return


incoming = {
    "element_name": "element",
    "time": 5,
    "action": "on_screen"
}

async def obs_worker(obs_queue):
    obs_websocketmanager = OBSWebsocketsManager()
    while True:
        if obs_queue.qsize() > 0:
            queue_item = obs_queue.get()
            element_name = queue_item.get("element_name", "")
            time = queue_item.get("time", 0)
            action = queue_item.get("action", "")
            if action == "on_screen":
                obs_websocketmanager.temp_display(element_name, time)
            await asyncio.sleep(0.1)
        await asyncio.sleep(0.1)

async def async_main():
    element_name = "DabiSpirations"
    obs_websocketmanager = OBSWebsocketsManager()
    response = obs_websocketmanager.ws.call(requests.GetCurrentProgramScene())
    current_scene_name = response.getSceneName()
    # print(obs_websocketmanager.source_checker("ingame"))
    print(f"{obs_websocketmanager.get_item_id(current_scene_name, element_name)=}")
    await obs_websocketmanager.temp_display(element_name, 15)

def main():
    element_name = "DabiSpirations"
    obs_websocketmanager = OBSWebsocketsManager()
    response = obs_websocketmanager.ws.call(requests.GetCurrentProgramScene())
    current_scene_name = response.getSceneName()
    # print(obs_websocketmanager.source_checker("ingame"))
    print(f"{obs_websocketmanager.get_item_id(current_scene_name, element_name)=}")
    start_time = time.time()
    rot = 0
    while time.time() < (start_time + 5):
        rot = 10*math.sin(12*time.time())
        obs_websocketmanager.shake(current_scene_name, element_name, rot)
    rot = 0
    obs_websocketmanager.shake(current_scene_name, element_name, rot)
    

if __name__ == "__main__":
    # main()
    asyncio.run(async_main())
import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import multiprocessing
import json
from typing import Any, List
import uuid, shutil, pathlib
from pathlib import Path

MEDIA_DIR = pathlib.Path("uploads")
MEDIA_DIR.mkdir(exist_ok=True)

BASE = Path(__file__).resolve().parent

def format_string_msg(msg_msg) -> str:
    formatted_return = {
        "msg_user": "Dabi",
        "msg_server": "Pdgeorge",
        "msg_msg": msg_msg,
        "formatted_msg": f"game:Dabi: {msg_msg}"
    }
    return formatted_return

def format_string_action(msg_msg) -> str:
    formatted_return = {
        "msg_user": "Dabi",
        "msg_server": "Pdgeorge",
        "msg_msg": msg_msg,
        "formatted_msg": f"action:Dabi: {msg_msg}"
    }
    return formatted_return

def format_string_website(msg_msg) -> str:
    formatted_return = {
        "msg_user": "Dabi",
        "msg_server": "Pdgeorge",
        "msg_msg": msg_msg,
        "formatted_msg": f"website:Dabi: {msg_msg}"
    }
    return formatted_return

def format_string_react(msg_msg, file_name) -> str:
    img_path = str(BASE / "uploads" / file_name)
    formatted_return = {
        "msg_user": "Dabi",
        "msg_server": "Pdgeorge",
        "msg_msg": msg_msg,
        "file_name": img_path,
        "formatted_msg": f"react:Dabi: {msg_msg}"
    }
    return formatted_return

def start_receiving(
        event_queue: multiprocessing.Queue,
        *,
        host: str = "0.0.0.0",
        port: int = 9000,
        log_level: str = "info",
    ) -> None:
    # The * FORCED everything after it to be called explicitly. IE: start_receiving(queue, host="127.0.0.1", port=8000)

    app = FastAPI(title="Game Event Receiver", version="1.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )

    @app.get("/health")
    async def health() -> dict[str, str]:  # noqa: D401 – simple verb is fine
        """Lightweight health-check endpoint for load balancers."""
        """
        For testing, use the following curl command, remember to update url and port as needed:
        curl -X GET http://0.0.0.0:9000/health
        """
        return {"status": "ok"}

    @app.post("/event")
    async def receive_event(request: Request) -> dict[str, str]:
        """Receive an event payload and push it onto the ``event_queue``."""
        """
        For testing, use the following curl command, remember to update url and port as needed:
        curl -X POST http://0.0.0.0:9000/event \
        -H "Content-Type: application/json" \
        -d '{"event_type":"TEST","msg_msg":"hello world"}'
        or
        curl -X POST http://0.0.0.0:9000/event \
        -H "Content-Type: application/json" \
        -d '{"event_type":"TEST","action":"reset"}'
        """
        try:
            payload: Any = await request.json()
        except Exception as exc:  # broad but safe here, we just reject bad JSON
            raise HTTPException(status_code=400, detail="Invalid JSON") from exc

        try:
            if payload.get('msg_msg', None):
                to_send = format_string_msg(payload.get('msg_msg', None))
                print(json.dumps(to_send))
                event_queue.put(json.dumps(to_send))
            if payload.get('action', None):
                to_send = format_string_action(payload.get('action', None))
                print(json.dumps(to_send))
                event_queue.put(json.dumps(to_send))
            if payload.get('website', None):
                to_send = format_string_website(payload.get('website', None))
                print(json.dumps(to_send))
                event_queue.put(json.dumps(to_send))
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Event queue full") from exc

        return {"status": "accepted"}

    @app.post("/review")
    async def receive_review(
        message: str = Form(...),
        uploads: List[UploadFile] = File(default=[]),
    ):
        if not message.strip():
            raise HTTPException(400, "Message is required")
        
        allowed = {".jpg", ".jpeg", ".png", ".gif", ".mp4", ".webm"}
        saved = []
        print(f"{message=}")
        for file in uploads:
            ext = pathlib.Path(file.filename).suffix.lower()
            if ext not in allowed:
                raise HTTPException(415, f"{file.filename}: unsupported type")
            
            uid = f"{uuid.uuid4()}{ext}"
            dest = MEDIA_DIR / uid
            with dest.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved.append(dest.name)
            file_name = str(dest.name)
            print(f"{file_name=}")
            to_send = format_string_react(message, file_name)
            event_queue.put(json.dumps(to_send))

        # Add "add_to_queue" sort of thing here, IDK
        # Alternative: The files are going to be piped in to a different model that "understands" what is inside of the files. 
        # It will describe their contents. That model will send the contents towards Dabi.
        # Choices: A) Listener that reacts whenever uploads folder receives a new file. 
        # B) An event that we send here TO the model to say "OI! Look for "this file"
        # I like A more, because then I can directly drop the file in without needing to upload through DabiBraincellFixer

        return {"ok": True, "files": saved}

    # Start the ASGI server (blocks until KeyboardInterrupt or process exit)
    uvicorn.run(app, host=host, port=port, log_level=log_level, access_log=True)

async def async_printer(gameplay_queue_test):
    while True:
        if gameplay_queue_test.qsize() > 0:
            temp_game_test = gameplay_queue_test.get()
            print(f"Received a message in test mode: {temp_game_test=}")
            print(f"Wait, let me try that again.")
            print(f"Here we go... {json.loads(temp_game_test)}")
            print(f"hardcoding test: {json.loads(temp_game_test).get('msg_msg', {})}")
        await asyncio.sleep(0.1)

def test_two(gameplay_queue_test):
    asyncio.run(async_printer(gameplay_queue_test=gameplay_queue_test))

def main_tester(gameplay_queue_test):
    start_receiving(gameplay_queue_test, host="127.0.0.1", port=8000)

def test_setup():
    gameplay_queue_test = multiprocessing.Queue()
    try:
        p1 = multiprocessing.Process(target=main_tester, args=(gameplay_queue_test,),)
        p1.start()
        p2 = multiprocessing.Process(target=test_two, args=(gameplay_queue_test,),)
        p2.start()
    except KeyboardInterrupt:
        print("Shutting down ...")
        p1.join(1)
        p1.terminate()
        p1.kill()
        p1.close()
        p2.join(1)
        p2.terminate()
        p2.kill()
        p2.close()

def queue_printer(event_queue: multiprocessing.Queue) -> None:
    """Continuously print events as they arrive in *event_queue*."""
    while True:
        event = event_queue.get()  # blocks until something is available
        print(f"[consumer] got event: {event}", flush=True)


# def main_tester() -> None:
#     """Launch the server in a background process and stream queue output."""
#     q: multiprocessing.Queue = multiprocessing.Queue()

#     server_proc = multiprocessing.Process(
#         target=start_receiving,
#         args=(q,),
#         kwargs={"host": "127.0.0.1", "port": 8000},
#         daemon=True,
#     )
#     server_proc.start()

#     print("Server listening on http://127.0.0.1:8000\nPress Ctrl+C to exit.")

#     try:
#         queue_printer(q)  # runs until Ctrl-C
#     except KeyboardInterrupt:
#         print("\nShutting down …", flush=True)
#         server_proc.terminate()
#         server_proc.join()


if __name__ == "__main__":
    test_setup()
    # main_tester()
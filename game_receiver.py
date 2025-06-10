
"""
FastAPI-based webhook receiver that pushes incoming JSON payloads into a
``multiprocessing.Queue``. Designed to be run in its own ``Process``.

Usage example (in your main program)::

    import multiprocessing as mp
    import game_receiver

    if __name__ == "__main__":
        event_queue = mp.Queue()
        receiver_proc = mp.Process(
            target=game_receiver.start_receiving,
            args=(event_queue,)
        )
        receiver_proc.start()
        # ... rest of your program ...

Every HTTP ``POST`` to http://<host>:<port>/event containing a JSON body will be
queued for your main process to consume.
"""
import asyncio
import uvicorn
from fastapi import FastAPI, HTTPException, Request
import multiprocessing
import json
from typing import Any

def format_string(msg_msg) -> str:
    formatted_return = {
        "msg_user": "Dabi",
        "msg_server": "Pdgeorge",
        "msg_msg": msg_msg,
        "formatted_msg": f"game:Dabi: {msg_msg}"
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

    @app.get("/health")
    async def health() -> dict[str, str]:  # noqa: D401 – simple verb is fine
        """Lightweight health‑check endpoint for load balancers."""
        return {"status": "ok"}

    @app.post("/event")
    async def receive_event(request: Request) -> dict[str, str]:
        """Receive an event payload and push it onto the ``event_queue``."""
        try:
            payload: Any = await request.json()
        except Exception as exc:  # broad but safe here, we just reject bad JSON
            raise HTTPException(status_code=400, detail="Invalid JSON") from exc

        try:
            if payload.get('msg_msg', None):
                to_send = format_string(payload.get('msg_msg', None))
                print(json.dumps(to_send))
                event_queue.put(json.dumps(to_send))
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Event queue full") from exc

        return {"status": "accepted"}

    # Start the ASGI server (blocks until KeyboardInterrupt or process exit)
    uvicorn.run(app, host=host, port=port, log_level=log_level, access_log=False)

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
#         queue_printer(q)  # runs until Ctrl‑C
#     except KeyboardInterrupt:
#         print("\nShutting down …", flush=True)
#         server_proc.terminate()
#         server_proc.join()


if __name__ == "__main__":
    test_setup()
    # main_tester()
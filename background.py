import asyncio, json, os, subprocess, sys
from event_bus import EventBus  # uses env vars internally

AMQP_URL = os.getenv("AMQP_URL", "amqp://guest:guest@localhost/")
ALLOW_AUTO = os.getenv("ALLOW_DOCKER_AUTOSTART", "0") == "1"

async def ensure_broker():
    try:
        print("waiting for broker?")
        bus = EventBus()
        await bus.connect()
        return bus
    except:
        print("docker compose uppies")
        subprocess.run(["docker", "compose", "up", "-d", "rabbitmq"], check=False)

    raise TimeoutError("RabbitMQ failed to start in time.")

def print_event(evt: dict):
    # Envelope
    print("— EVENT —")
    print(f"id:                {evt.get('id')}")
    print(f"type:              {evt.get('type')}")
    print(f"source:            {evt.get('source')}")
    print(f"time:              {evt.get('time')}")
    print(f"specversion:       {evt.get('specversion')}")
    print(f"datacontenttype:   {evt.get('datacontenttype')}")

    data = evt.get("data", {}) or {}
    print("— DATA —")
    print(f"reward_title:      {data.get('reward_title')}")
    print(f"reward_id:         {data.get('reward_id')}")
    print(f"user:              {data.get('user')}")
    print(f"user_input:        {data.get('user_input')}")
    print(f"cost:              {data.get('cost')}")
    print(f"{evt=}")
    print(f"{data=}")
    print("-----------------------------", flush=True)

def test_routing(evt, rk):
    if rk == "redeem.test":
        print("rk: redeem.test")
        print_event(evt)

    if rk == "redeem.inspire":
        print("rk: redeem.inspire")
        print_event(evt)

    if rk == "redeem.brb":
        print("rk: redeem.brb")
        print_event(evt)

    if rk == "redeem.talk":
        print("rk: redeem.talk")
        print_event(evt)

async def run():
    
    bus = await ensure_broker()

    q = await bus.bind_queue(queue_name="background", pattern="#") # Will do ALL redeems

    # Examples of individual subscriptions
    # q = await bus.bind_queue(queue_name="background", pattern="redeem.test")
    # q = await bus.bind_queue(queue_name="background", pattern="redeem.inspire")
    # q = await bus.bind_queue(queue_name="background", pattern="redeem.brb")
    # q = await bus.bind_queue(queue_name="background", pattern="redeem.talk")

    # More examples
    # q = await bus.bind_queue(queue_name="background", pattern="redeem.*") # Will do all of the above, but not redeem.a.b
    # q = await bus.bind_queue(queue_name="background", pattern="redeem.#") # Will do all of the above, even redeem.a.b

    print("[background] waiting for redemptions...")

    async with q.iterator() as it:
        async for msg in it:
            try:
                evt = json.loads(msg.body)
                rk = msg.routing_key

                # Test routing (duh)
                test_routing(evt, rk)

                await msg.ack()
            except Exception as e:
                print("[background] handler error:", e)
                await msg.reject(requeue=False)

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception as e:
        print("[background] fatal:", e)
        sys.exit(1)

# event_bus.py
import os, json, uuid, aio_pika
from datetime import datetime, timezone


AMQP_URL = os.getenv("AMQP_URL", "amqp://guest:guest@localhost/")
EXCHANGE_NAME = os.getenv("EXCHANGE_NAME", "dabi.events")
DLX_NAME = os.getenv("DLX_NAME", "dabi.dlx")

import asyncio
import subprocess

async def ensure_broker():
    try:
        print("Waiting for broker connection...")
        bus = EventBus()
        await bus.connect()
        return bus
    except Exception:
        print("RabbitMQ not running — starting via Docker Compose...")
        subprocess.run(["docker", "compose", "up", "-d", "rabbitmq"], check=False)

        # Wait for RabbitMQ container to become healthy
        for _ in range(30):  # ~30 × 2s = 60s max wait
            status = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Health.Status}}", "rabbitmq"],
                capture_output=True,
                text=True
            )
            if "healthy" in status.stdout:
                print("RabbitMQ is healthy.")
                break
            print("Waiting for RabbitMQ to become healthy...")
            await asyncio.sleep(2)
        else:
            raise TimeoutError("RabbitMQ failed to reach healthy state in time.")

        # Once healthy, connect to the event bus
        bus = EventBus()
        await bus.connect()
        return bus

class EventBus:
    def __init__(self):
        self._conn = None
        self._ch = None
        self._ex = None

    async def connect(self):
        if self._conn:
            return
        # robust = auto-reconnects on broker restarts
        self._conn = await aio_pika.connect_robust(AMQP_URL)
        self._ch = await self._conn.channel()
        self._ex = await self._ch.declare_exchange(
            EXCHANGE_NAME, aio_pika.ExchangeType.TOPIC, durable=True
        )
        # Dead-letter exchange in case you add DLQs later
        await self._ch.declare_exchange(DLX_NAME, aio_pika.ExchangeType.TOPIC, durable=True)

    async def publish(self, routing_key: str, type_: str, data: dict, source: str):
        """Publish a CloudEvents-style JSON message."""
        evt = {
            "specversion": "1.0",
            "id": str(uuid.uuid4()),
            "source": source,
            "type": type_,
            "time": datetime.now(timezone.utc).isoformat(),
            "datacontenttype": "application/json",
            "data": data,
        }
        msg = aio_pika.Message(
            body=json.dumps(evt).encode("utf-8"),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await self._ex.publish(msg, routing_key=routing_key)

    async def bind_queue(self, queue_name: str, pattern: str):
        """Declare a durable queue and bind it to the topic exchange with a routing pattern."""
        args = {"x-dead-letter-exchange": DLX_NAME}
        q = await self._ch.declare_queue(queue_name, durable=True, arguments=args)
        await q.bind(self._ex, routing_key=pattern)
        return q

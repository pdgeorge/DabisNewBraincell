# event_bus.py
import os, json, uuid, aio_pika
from datetime import datetime, timezone


AMQP_URL = os.getenv("AMQP_URL", "amqp://guest:guest@localhost/")
EXCHANGE_NAME = os.getenv("EXCHANGE_NAME", "dabi.events")
DLX_NAME = os.getenv("DLX_NAME", "dabi.dlx")

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

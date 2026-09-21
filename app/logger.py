import json
import logging
import os
from pathlib import Path

from app.messaging import LOGGER_QUEUE, connect, declare_logger_queue

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logging.getLogger("pika").setLevel(logging.WARNING)
log = logging.getLogger(__name__)
LOG_FILE = Path("/app/logs/events.jsonl")


def handle_message(channel, method, properties, body):
    try:
        event = json.loads(body)
        if not isinstance(event, dict):
            raise ValueError("event must be a JSON object")
    except ValueError as error:
        log.error("Rejecting invalid event: %s", error)
        channel.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
        return

    record = {"routing_key": method.routing_key, "event": event}
    with LOG_FILE.open("a", encoding="utf-8") as output:
        output.write(json.dumps(record) + "\n")
        output.flush()
        os.fsync(output.fileno())

    channel.basic_ack(delivery_tag=method.delivery_tag)
    log.info("Logged event with routing key %s", method.routing_key)


def main():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    declare_logger_queue()
    connection = connect()
    try:
        channel = connection.channel()
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(
            queue=LOGGER_QUEUE,
            on_message_callback=handle_message,
            auto_ack=False,
        )
        log.info("Waiting for events on %s", LOGGER_QUEUE)
        channel.start_consuming()
    except KeyboardInterrupt:
        log.info("Stopping logger")
    finally:
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()

import json
import logging

from app.messaging import NOTIFIER_QUEUE, connect, declare_notifier_queue

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logging.getLogger("pika").setLevel(logging.WARNING)
log = logging.getLogger(__name__)


def handle_message(channel, method, properties, body):
    try:
        event = json.loads(body)
        if not isinstance(event, dict):
            raise ValueError("event must be a JSON object")
    except ValueError as error:
        log.error("Rejecting invalid notification event: %s", error)
        channel.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
        return

    log.info("Would notify for %s: %s", method.routing_key, json.dumps(event))
    channel.basic_ack(delivery_tag=method.delivery_tag)


def main():
    declare_notifier_queue()
    connection = connect()
    try:
        channel = connection.channel()
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(
            queue=NOTIFIER_QUEUE,
            on_message_callback=handle_message,
            auto_ack=False,
        )
        log.info("Waiting for events on %s", NOTIFIER_QUEUE)
        channel.start_consuming()
    except KeyboardInterrupt:
        log.info("Stopping notifier")
    finally:
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()

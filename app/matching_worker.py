import json
import logging

from messaging import MATCHING_QUEUE, connect

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logging.getLogger("pika").setLevel(logging.WARNING)
log = logging.getLogger(__name__)


def handle_message(channel, method, properties, body):
    try:
        job = json.loads(body)
        if not isinstance(job, dict):
            raise ValueError("job must be a JSON object")
        item_id = job.get("item_id")
        if type(item_id) is not int or item_id <= 0:
            raise ValueError("item_id must be a positive integer")
    except (ValueError, UnicodeDecodeError) as error:
        log.error("Rejecting invalid matching job: %s", error)
        channel.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
        return

    log.info("Received item %s matching is not implemented yet", item_id)
    channel.basic_ack(delivery_tag=method.delivery_tag)


def main():
    connection = connect()
    try:
        channel = connection.channel()
        channel.queue_declare(queue=MATCHING_QUEUE, durable=True)
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(
            queue=MATCHING_QUEUE,
            on_message_callback=handle_message,
            auto_ack=False,
        )
        log.info("Waiting for jobs on %s", MATCHING_QUEUE)
        channel.start_consuming()
    except KeyboardInterrupt:
        log.info("Stopping matching worker")
    finally:
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()

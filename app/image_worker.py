import json
import logging

from app.messaging import IMAGE_QUEUE, connect

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
        image_ref = job.get("image_ref")
        if not isinstance(image_ref, str) or not image_ref.strip():
            raise ValueError("image_ref must be a non-empty string")
    except (ValueError, UnicodeDecodeError) as error:
        log.error("Rejecting invalid image job: %s", error)
        channel.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
        return

    log.info(
        "Received image %s for item %s image processing is not implemented yet",
        image_ref,
        item_id,
    )
    channel.basic_ack(delivery_tag=method.delivery_tag)


def main():
    connection = connect()
    try:
        channel = connection.channel()
        channel.queue_declare(queue=IMAGE_QUEUE, durable=True)
        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(
            queue=IMAGE_QUEUE,
            on_message_callback=handle_message,
            auto_ack=False,
        )
        log.info("Waiting for jobs on %s", IMAGE_QUEUE)
        channel.start_consuming()
    except KeyboardInterrupt:
        log.info("Stopping image worker")
    finally:
        if connection.is_open:
            connection.close()


if __name__ == "__main__":
    main()

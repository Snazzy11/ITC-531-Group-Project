import json
import logging

import crud
import image_processing
from database.database import SessionLocal
from database.models import ImageStatus
from image_processing import Rejected
from messaging import IMAGE_QUEUE, connect
from ports import storage

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logging.getLogger("pika").setLevel(logging.WARNING)
logging.getLogger("botocore").setLevel(logging.WARNING)
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

    process(item_id, image_ref)
    channel.basic_ack(delivery_tag=method.delivery_tag)


def process(item_id: int, upload_id: str) -> None:
    """Safe to run twice for the same upload: a redelivered job finds the row
    already finished and stops, and a crash before that just redoes the work
    onto the same key."""
    pending = storage.pending_key(upload_id)
    with SessionLocal() as db:
        image = crud.get_image(db, item_id, upload_id)
        if image is None or image.status in (ImageStatus.READY, ImageStatus.REJECTED):
            log.info("Upload %s for item %s needs no work", upload_id, item_id)
            return

        try:
            data = storage.read(pending, image_processing.MAX_UPLOAD_BYTES)
            if data is None:
                raise Rejected("no upload was found")
            image_processing.check_size(data)
            content_type = image_processing.detect_type(data)
            photo = image_processing.reencode(data)
        except Rejected as reason:
            crud.mark_image_rejected(db, image, str(reason))
            storage.delete(pending)
            log.info("Rejected upload %s for item %s: %s", upload_id, item_id, reason)
            return

        key = storage.photo_key(item_id, upload_id)
        storage.write(key, photo, "image/jpeg", upload_id)
        for old_key in crud.mark_image_ready(db, image, key, content_type, len(data)):
            storage.delete(old_key)
        storage.delete(pending)
        log.info("Stored %s (%s, %d bytes in)", key, content_type, len(data))


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

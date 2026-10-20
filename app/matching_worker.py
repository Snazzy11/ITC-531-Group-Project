import json
import logging

import crud
from database.database import SessionLocal
from database.models import Item, ItemStatus, ItemType, PotentialMatch
from matching import matcher
from matching.match_score import MatchScore
from messaging import MATCHING_QUEUE, connect, emit_event

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logging.getLogger("pika").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

SOURCE = "matching-worker"


def handle_message(channel, method, properties, body):
    try:
        job = json.loads(body)
        if not isinstance(job, dict):
            raise TypeError("job must be a JSON object")
        item_id = job.get("item_id")
        if type(item_id) is not int or item_id <= 0:
            raise ValueError("item_id must be a positive integer")
    except (TypeError, ValueError, UnicodeDecodeError) as error:
        log.error("Rejecting invalid matching job: %s", error)
        channel.basic_reject(delivery_tag=method.delivery_tag, requeue=False)
        return

    process(item_id)
    channel.basic_ack(delivery_tag=method.delivery_tag)


def process(item_id: int) -> None:
    """Safe to run twice for the same item: it replaces the item's suggestions,
    and only pairs it had not suggested before are announced."""
    with SessionLocal() as db:
        item = crud.get_item(db, item_id)
        if item is None or item.status is not ItemStatus.OPEN:
            log.info("Item %s is gone or not open; nothing to match", item_id)
            return

        rows = [to_row(item, score) for score in matcher.get_potential_matches(db, item_id)]
        new = crud.replace_potential_matches(db, item_id, rows)
        payloads = [
            {"lost_item_id": r.lost_item_id, "found_item_id": r.found_item_id, "score": r.score}
            for r in new
        ]

    # Best-effort: the suggestions are already saved, so a broker hiccup only
    # costs the notification.
    for payload in payloads:
        emit_event("match.potential_found", payload, source=SOURCE)
    log.info("Item %s: %d suggestions, %d new", item_id, len(rows), len(payloads))


def to_row(item: Item, score: MatchScore) -> PotentialMatch:
    if item.type == ItemType.LOST:
        lost_id, found_id = item.id, score.candidate_item_id
    else:
        lost_id, found_id = score.candidate_item_id, item.id
    return PotentialMatch(lost_item_id=lost_id, found_item_id=found_id, score=score.score)


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

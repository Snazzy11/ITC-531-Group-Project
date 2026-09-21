import json
import os

import pika

from app.events import build_event

MATCHING_QUEUE = "jobs.item_matcher"
IMAGE_QUEUE = "jobs.image_processor"
EVENT_EXCHANGE = "seekr.events"
LOGGER_QUEUE = "events.logger"
NOTIFIER_QUEUE = "events.notifier"
NOTIFIER_BINDINGS = ("match.potential_found", "match.confirmed")


def connect() -> pika.BlockingConnection:
    credentials = pika.PlainCredentials(
        os.environ["BROKER_USER"], os.environ["BROKER_PASSWORD"]
    )
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host=os.environ["BROKER_HOST"], credentials=credentials
        )
    )


def declare_matching_queue() -> None:
    connection = connect()
    try:
        channel = connection.channel()
        channel.queue_declare(queue=MATCHING_QUEUE, durable=True)
        print(f"Declared durable queue: {MATCHING_QUEUE}")
    finally:
        connection.close()


def publish_matching_job(item_id: int) -> None:
    if type(item_id) is not int or item_id <= 0:
        raise ValueError("item_id must be a positive integer")

    connection = connect()
    try:
        channel = connection.channel()
        channel.queue_declare(queue=MATCHING_QUEUE, durable=True)
        channel.confirm_delivery()
        channel.basic_publish(
            exchange="",
            routing_key=MATCHING_QUEUE,
            body=json.dumps({"item_id": item_id}).encode("utf-8"),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
            ),
            mandatory=True,
        )
        print(f"Published matching job for item {item_id}")
    finally:
        connection.close()


def declare_image_queue() -> None:
    connection = connect()
    try:
        channel = connection.channel()
        channel.queue_declare(queue=IMAGE_QUEUE, durable=True)
        print(f"Declared durable queue: {IMAGE_QUEUE}")
    finally:
        connection.close()


def publish_image_job(item_id: int, image_ref: str) -> None:
    if type(item_id) is not int or item_id <= 0:
        raise ValueError("item_id must be a positive integer")
    if not isinstance(image_ref, str) or not image_ref.strip():
        raise ValueError("image_ref must be a non-empty string")

    connection = connect()
    try:
        channel = connection.channel()
        channel.queue_declare(queue=IMAGE_QUEUE, durable=True)
        channel.confirm_delivery()
        channel.basic_publish(
            exchange="",
            routing_key=IMAGE_QUEUE,
            body=json.dumps({"item_id": item_id, "image_ref": image_ref}).encode("utf-8"),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
            ),
            mandatory=True,
        )
        print(f"Published image job for item {item_id}")
    finally:
        connection.close()


def declare_event_exchange() -> None:
    connection = connect()
    try:
        channel = connection.channel()
        channel.exchange_declare(
            exchange=EVENT_EXCHANGE,
            exchange_type="topic",
            durable=True,
        )
        print(f"Declared durable topic exchange: {EVENT_EXCHANGE}")
    finally:
        connection.close()


def publish_event(
    event_type: str, payload: dict, source: str = "campus-seekr-api"
) -> str:
    event = build_event(event_type, payload, source)
    event_id = str(event.event_id)
    body = event.model_dump_json().encode("utf-8")

    connection = connect()
    try:
        channel = connection.channel()
        channel.exchange_declare(
            exchange=EVENT_EXCHANGE,
            exchange_type="topic",
            durable=True,
        )
        channel.confirm_delivery()
        channel.basic_publish(
            exchange=EVENT_EXCHANGE,
            routing_key=event_type,
            body=body,
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
                message_id=event_id,
            ),
            mandatory=True,
        )
        print(f"Published event {event_type}: {event_id}")
        return event_id
    finally:
        connection.close()


def declare_logger_queue() -> None:
    connection = connect()
    try:
        channel = connection.channel()
        channel.exchange_declare(
            exchange=EVENT_EXCHANGE,
            exchange_type="topic",
            durable=True,
        )
        channel.queue_declare(queue=LOGGER_QUEUE, durable=True)
        channel.queue_bind(
            queue=LOGGER_QUEUE,
            exchange=EVENT_EXCHANGE,
            routing_key="#",
        )
        print(f"Declared logger queue: {LOGGER_QUEUE}, bound to {EVENT_EXCHANGE}")
    finally:
        connection.close()


def declare_notifier_queue() -> None:
    connection = connect()
    try:
        channel = connection.channel()
        channel.exchange_declare(
            exchange=EVENT_EXCHANGE,
            exchange_type="topic",
            durable=True,
        )
        channel.queue_declare(queue=NOTIFIER_QUEUE, durable=True)
        for routing_key in NOTIFIER_BINDINGS:
            channel.queue_bind(
                queue=NOTIFIER_QUEUE,
                exchange=EVENT_EXCHANGE,
                routing_key=routing_key,
            )
        print(f"Declared notifier queue: {NOTIFIER_QUEUE}")
    finally:
        connection.close()


if __name__ == "__main__":
    declare_matching_queue()
    declare_image_queue()
    declare_event_exchange()
    declare_logger_queue()
    declare_notifier_queue()

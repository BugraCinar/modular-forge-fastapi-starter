import json
import logging

from kafka import KafkaProducer

logger = logging.getLogger(__name__)


class KafkaEvents:
    def __init__(self, settings):
        options = {
            "bootstrap_servers": settings.kafka_bootstrap_servers.split(","),
            "security_protocol": settings.kafka_security_protocol,
            "acks": "all",
            "retries": 3,
            "max_block_ms": 5000,
            "request_timeout_ms": 10000,
            "value_serializer": lambda value: json.dumps(value).encode(),
            "key_serializer": lambda key: key.encode(),
        }
        if settings.kafka_security_protocol == "SASL_SSL":
            options.update(
                sasl_mechanism="PLAIN",
                sasl_plain_username=settings.kafka_sasl_username,
                sasl_plain_password=settings.kafka_sasl_password,
            )
        self.producer = KafkaProducer(**options)
        self.topic = settings.kafka_topic

    def publish(self, event):
        try:
            self.producer.send(self.topic, key=event["account_id"], value=event).get(timeout=10)
        except Exception:
            logger.error("Kafka delivery failed; event_id=%s", event["id"])

    def close(self):
        self.producer.close(timeout=5)

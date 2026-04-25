import pika
import os
import logging

# Configure basic logging for publisher module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

def get_rabbitmq_connection():
    """
    Establishes and returns a blocking connection to RabbitMQ.
    """
    logger.debug(f"Attempting to connect to RabbitMQ at {RABBITMQ_URL}")
    try:
        parameters = pika.URLParameters(RABBITMQ_URL)
        connection = pika.BlockingConnection(parameters)
        logger.info("Successfully connected to RabbitMQ.")
        return connection
    except Exception as e:
        logger.error(f"Failed to connect to RabbitMQ: {e}", exc_info=True)
        raise
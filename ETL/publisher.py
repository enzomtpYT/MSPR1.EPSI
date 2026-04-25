import pika
import os

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

def get_rabbitmq_connection():
    parameters = pika.URLParameters(RABBITMQ_URL)
    return pika.BlockingConnection(parameters)
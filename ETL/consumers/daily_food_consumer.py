import pika
import json
import os
import logging
from pydantic import ValidationError
from src.database import SessionLocal
from src.models.product import Product
from src.etl.schemas import DailyFoodRow

# Configure logging for this consumer
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

def process_message(ch, method, properties, body):
    logger.info("Received message from daily_food_queue.")
    try:
        # Parse and validate the incoming JSON message
        data = json.loads(body)
        row = DailyFoodRow(**data)
        logger.debug(f"Message parsed successfully for food item: {row.Food_Item}")
    except (ValidationError, json.JSONDecodeError) as e:
        logger.error(f"Failed to parse or validate message: {e}")
        # Acknowledge the message so it doesn't get stuck in the queue
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    db = SessionLocal()
    try:
        # Map the validated data to the Product ORM model
        product = Product(
            product_name=row.Food_Item,
            product_kcal=row.Calories,
            product_protein=row.Protein,
            product_carbs=row.Carbohydrates,
            product_fat=row.Fat,
            product_fiber=row.Fiber,
            product_sugar=row.Sugars,
            product_sodium=row.Sodium,
            product_chol=row.Cholesterol,
            Product_Diet_Tags=row.Category,
            Product_Price_Category=row.Meal_Type
        )
        # Persist the new product to the database
        db.add(product)
        db.commit()
        logger.info(f"Product '{row.Food_Item}' successfully saved to database.")
    except Exception as e:
        # Roll back the transaction if any database error occurs
        db.rollback()
        logger.error(f"Database error while saving product '{row.Food_Item}': {e}", exc_info=True)
    finally:
        # Ensure database resources are released and message is acknowledged
        db.close()
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.debug("Database session closed and message acknowledged.")

def start():
    logger.info("Starting daily_food_consumer...")
    try:
        # Establish connection to the RabbitMQ server
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        channel = connection.channel()
        channel.queue_declare(queue="daily_food_queue", durable=True)
        
        # Configure quality of service to prevent overloading the consumer
        channel.basic_qos(prefetch_count=10)
        channel.basic_consume(queue="daily_food_queue", on_message_callback=process_message)
        
        logger.info("Connected to RabbitMQ. Waiting for messages on daily_food_queue.")
        channel.start_consuming()
    except Exception as e:
        logger.critical(f"Failed to start daily_food_consumer: {e}", exc_info=True)

if __name__ == "__main__":
    start()
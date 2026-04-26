import pika
import json
import os
import sys
import logging
import psycopg2
from pydantic import ValidationError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from schemas import DailyFoodRow

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://rabbit:rabbit_password@rabbitmq:5672/")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@database:5432/etl_db")

def process_message(ch, method, properties, body):
    logger.info("Received message from daily_food_queue.")
    try:
        data = json.loads(body)
        row = DailyFoodRow(**data)
        logger.debug(f"Message parsed successfully for food item: {row.Food_Item}")
    except (ValidationError, json.JSONDecodeError) as e:
        logger.error(f"Failed to parse or validate message: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO products (
                product_name, product_kcal, product_protein, product_carbs, 
                product_fat, product_fiber, product_sugar, product_sodium, 
                product_chol, "Product_Diet_Tags", "Product_Price_Category"
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            row.Food_Item, row.Calories, row.Protein, row.Carbohydrates,
            row.Fat, row.Fiber, row.Sugars, row.Sodium, row.Cholesterol,
            row.Category, row.Meal_Type
        ))
        
        conn.commit()
        cur.close()
        logger.info(f"Product '{row.Food_Item}' successfully saved to database container.")
    except Exception as e:
        if conn is not None:
            conn.rollback()
        logger.error(f"Database error while saving product '{row.Food_Item}': {e}", exc_info=True)
    finally:
        if conn is not None:
            conn.close()
        ch.basic_ack(delivery_tag=method.delivery_tag)

def start():
    logger.info("Starting daily_food_consumer...")
    try:
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        channel = connection.channel()
        channel.queue_declare(queue="daily_food_queue", durable=True)
        channel.basic_qos(prefetch_count=10)
        channel.basic_consume(queue="daily_food_queue", on_message_callback=process_message)
        logger.info("Connected to RabbitMQ. Waiting for messages on daily_food_queue.")
        channel.start_consuming()
    except Exception as e:
        logger.critical(f"Failed to start daily_food_consumer: {e}", exc_info=True)

if __name__ == "__main__":
    start()
import pika
import json
import os
from pydantic import ValidationError
from src.database import SessionLocal
from src.models.product import Product
from src.etl.schemas import DailyFoodRow

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

def process_message(ch, method, properties, body):
    try:
        data = json.loads(body)
        row = DailyFoodRow(**data)
    except (ValidationError, json.JSONDecodeError):
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    db = SessionLocal()
    try:
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
        db.add(product)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
        ch.basic_ack(delivery_tag=method.delivery_tag)

def start():
    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    channel = connection.channel()
    channel.queue_declare(queue="daily_food_queue", durable=True)
    channel.basic_qos(prefetch_count=10)
    channel.basic_consume(queue="daily_food_queue", on_message_callback=process_message)
    channel.start_consuming()

if __name__ == "__main__":
    start()
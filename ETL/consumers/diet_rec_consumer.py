import pika
import json
import os
import sys
import logging
from datetime import datetime
import psycopg2
from pydantic import ValidationError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from schemas import DietRecRow

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://rabbit:rabbit_password@rabbitmq:5672/")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@database:5432/etl_db")

def process_message(ch, method, properties, body):
    logger.info("Received message from diet_rec_queue.")
    try:
        data = json.loads(body)
        row = DietRecRow(**data)
        logger.debug(f"Message parsed successfully for patient ID: {row.Patient_ID}")
    except (ValidationError, json.JSONDecodeError) as e:
        logger.error(f"Validation or decoding error: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        now = datetime.utcnow()
        
        user_mail = f"patient_{row.Patient_ID}@etl.local"
        height = row.Height_cm / 100.0 if row.Height_cm > 3.0 else row.Height_cm
        
        cur.execute('SELECT "User_ID" FROM users WHERE "User_mail" = %s', (user_mail,))
        user_record = cur.fetchone()

        if not user_record:
            logger.info(f"User {user_mail} not found. Creating new user.")
            cur.execute("""
                INSERT INTO users (
                    "User_mail", "User_password", "User_age", "User_gender", "User_weight", 
                    "User_Height", "User_Allergies", "User_Dietary_Preferences", "User_Goals", created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user_mail, "ETL_GENERATED_PASSWORD", row.Age, row.Gender, 
                row.Weight_kg, height, row.Allergies, 
                row.Dietary_Restrictions, row.Diet_Recommendation, now, now
            ))
        else:
            logger.info(f"User {user_mail} found. Updating existing records.")
            cur.execute("""
                UPDATE users 
                SET "User_age" = %s, "User_gender" = %s, "User_weight" = %s, 
                    "User_Height" = %s, "User_Allergies" = %s, "User_Dietary_Preferences" = %s, 
                    "User_Goals" = %s, updated_at = %s
                WHERE "User_mail" = %s
            """, (
                row.Age, row.Gender, row.Weight_kg, height, row.Allergies, 
                row.Dietary_Restrictions, row.Diet_Recommendation, now, user_mail
            ))

        conn.commit()
        cur.close()
        logger.info(f"Database transaction committed for user: {user_mail}")
    except Exception as e:
        if conn is not None:
            conn.rollback()
        logger.error(f"Database error while processing patient {row.Patient_ID}: {e}", exc_info=True)
    finally:
        if conn is not None:
            conn.close()
        ch.basic_ack(delivery_tag=method.delivery_tag)

def start():
    logger.info("Starting diet_rec_consumer...")
    try:
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        channel = connection.channel()
        channel.queue_declare(queue="diet_rec_queue", durable=True)
        channel.basic_qos(prefetch_count=10)
        channel.basic_consume(queue="diet_rec_queue", on_message_callback=process_message)
        logger.info("Connected to RabbitMQ. Waiting for messages on diet_rec_queue.")
        channel.start_consuming()
    except Exception as e:
        logger.critical(f"Failed to start diet_rec_consumer: {e}", exc_info=True)

if __name__ == "__main__":
    start()
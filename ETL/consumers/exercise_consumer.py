import pika
import json
import os
import sys
import uuid
import logging
import psycopg2
from datetime import datetime, timezone
from pydantic import ValidationError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from schemas import ExerciseRow

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://rabbit:rabbit_password@rabbitmq:5672/")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@database:5432/etl_db")

def process_message(ch, method, properties, body):
    logger.info("Received message from exercise_queue.")
    try:
        data = json.loads(body)
        row = ExerciseRow(**data)
    except (ValidationError, json.JSONDecodeError) as e:
        logger.error(f"Message parsing failed: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        user_mail = f"tracker_{uuid.uuid4().hex[:8]}@etl.local"
        logger.info(f"Registering new tracker user: {user_mail}")
        
        cur.execute("""
            INSERT INTO users (
                user_mail, user_password, user_age, user_gender, user_weight, user_height
            ) VALUES (%s, %s, %s, %s, %s, %s) RETURNING user_id
        """, (user_mail, "ETL_GENERATED_PASSWORD", row.Age, row.Gender, row.Weight, row.Height))
        
        user_id = cur.fetchone()[0]
        
        duration_minutes = int(row.Session_Duration * 60)
        today = datetime.now(timezone.utc).date()

        cur.execute("""
            INSERT INTO workout_sessions (
                user_id, session_date, session_maxbpm, session_avgbpm, 
                session_restingbpm, session_duration, session_type
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (user_id, today, row.Max_BPM, row.Avg_BPM, row.Resting_BPM, duration_minutes, row.Workout_Type))
        
        cur.execute("""
            INSERT INTO biometrics_logs (
                user_id, log_date, weight, heart_rate
            ) VALUES (%s, %s, %s, %s)
        """, (user_id, today, row.Weight, row.Avg_BPM))

        conn.commit()
        cur.close()
        logger.info(f"Successfully processed exercise data for user {user_id}.")
    except Exception as e:
        if conn is not None:
            conn.rollback()
        logger.error(f"Database error while saving exercise data: {e}", exc_info=True)
    finally:
        if conn is not None:
            conn.close()
        ch.basic_ack(delivery_tag=method.delivery_tag)

def start():
    logger.info("Starting exercise_consumer...")
    try:
        connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
        channel = connection.channel()
        channel.queue_declare(queue="exercise_queue", durable=True)
        channel.basic_qos(prefetch_count=10)
        channel.basic_consume(queue="exercise_queue", on_message_callback=process_message)
        logger.info("Connected to RabbitMQ. Waiting for messages on exercise_queue.")
        channel.start_consuming()
    except Exception as e:
        logger.critical(f"Failed to start exercise_consumer: {e}", exc_info=True)

if __name__ == "__main__":
    start()
import pika
import json
import os
import uuid
import logging
from datetime import datetime, timezone
from pydantic import ValidationError
from src.database import SessionLocal
from src.models.user import User
from src.models.workout_session import WorkoutSession
from src.models.biometrics_log import BiometricsLog
from src.etl.schemas import ExerciseRow

# Configure logging for this consumer
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

def process_message(ch, method, properties, body):
    logger.info("Received message from exercise_queue.")
    try:
        data = json.loads(body)
        row = ExerciseRow(**data)
        logger.debug("Exercise message parsed successfully.")
    except (ValidationError, json.JSONDecodeError) as e:
        logger.error(f"Message parsing failed: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    db = SessionLocal()
    try:
        # Generate a unique email for tracker data mapping
        user_mail = f"tracker_{uuid.uuid4().hex[:8]}@etl.local"
        logger.info(f"Registering new tracker user: {user_mail}")
        
        user = User(
            User_mail=user_mail,
            User_password="ETL_GENERATED_PASSWORD",
            User_age=row.Age,
            User_gender=row.Gender,
            User_weight=row.Weight,
            User_Height=row.Height
        )
        db.add(user)
        db.commit()
        # Refresh to obtain the generated User_ID
        db.refresh(user)

        # Convert hours to minutes for standard session tracking
        duration_minutes = int(row.Session_Duration * 60)
        today = datetime.now(timezone.utc).date()

        # Create a new workout session record
        session = WorkoutSession(
            User_ID=user.User_ID,
            Session_Date=today,
            Session_MaxBpm=row.Max_BPM,
            Session_AvgBpm=row.Avg_BPM,
            Session_RestingBpm=row.Resting_BPM,
            Session_Duration=duration_minutes,
            Session_Type=row.Workout_Type
        )
        db.add(session)
        logger.debug(f"Workout session added for User_ID: {user.User_ID}")

        # Create a biometrics log entry
        biometrics = BiometricsLog(
            User_ID=user.User_ID,
            Log_Date=today,
            Weight=row.Weight,
            Heart_Rate=row.Avg_BPM
        )
        db.add(biometrics)
        logger.debug(f"Biometrics log added for User_ID: {user.User_ID}")

        db.commit()
        logger.info(f"Successfully processed exercise data for user {user.User_ID}.")
    except Exception as e:
        db.rollback()
        logger.error(f"Database error while saving exercise data: {e}", exc_info=True)
    finally:
        db.close()
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
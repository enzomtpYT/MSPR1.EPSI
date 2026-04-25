import pika
import json
import os
import logging
from pydantic import ValidationError
from src.database import SessionLocal
from src.models.user import User
from src.etl.schemas import DietRecRow

# Configure logging for this consumer
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

def process_message(ch, method, properties, body):
    logger.info("Received message from diet_rec_queue.")
    try:
        # Deserialize and validate incoming payload
        data = json.loads(body)
        row = DietRecRow(**data)
        logger.debug(f"Message parsed successfully for patient ID: {row.Patient_ID}")
    except (ValidationError, json.JSONDecodeError) as e:
        logger.error(f"Validation or decoding error: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    db = SessionLocal()
    try:
        user_mail = f"patient_{row.Patient_ID}@etl.local"
        
        # Check if the user already exists in the database
        user = db.query(User).filter(User.User_mail == user_mail).first()

        if not user:
            logger.info(f"User {user_mail} not found. Creating new user.")
            user = User(
                User_mail=user_mail,
                User_password="ETL_GENERATED_PASSWORD",
                User_age=row.Age,
                User_gender=row.Gender,
                User_weight=row.Weight_kg,
                # Normalize height to meters if provided in centimeters
                User_Height=row.Height_cm / 100.0 if row.Height_cm > 3.0 else row.Height_cm,
                User_Allergies=row.Allergies,
                User_Dietary_Preferences=row.Dietary_Restrictions,
                User_Goals=row.Diet_Recommendation
            )
            db.add(user)
        else:
            logger.info(f"User {user_mail} found. Updating existing records.")
            user.User_age = row.Age
            user.User_gender = row.Gender
            user.User_weight = row.Weight_kg
            # Normalize height to meters if provided in centimeters
            user.User_Height = row.Height_cm / 100.0 if row.Height_cm > 3.0 else row.Height_cm
            user.User_Allergies = row.Allergies
            user.User_Dietary_Preferences = row.Dietary_Restrictions
            user.User_Goals = row.Diet_Recommendation

        db.commit()
        logger.info(f"Database transaction committed for user: {user_mail}")
    except Exception as e:
        db.rollback()
        logger.error(f"Database error while processing patient {row.Patient_ID}: {e}", exc_info=True)
    finally:
        db.close()
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.debug("Cleaned up resources and acknowledged message.")

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
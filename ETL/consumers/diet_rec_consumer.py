import pika
import json
import os
from pydantic import ValidationError
from src.database import SessionLocal
from src.models.user import User
from src.etl.schemas import DietRecRow

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

def process_message(ch, method, properties, body):
    try:
        data = json.loads(body)
        row = DietRecRow(**data)
    except (ValidationError, json.JSONDecodeError):
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    db = SessionLocal()
    try:
        user_mail = f"patient_{row.Patient_ID}@etl.local"
        user = db.query(User).filter(User.User_mail == user_mail).first()

        if not user:
            user = User(
                User_mail=user_mail,
                User_password="ETL_GENERATED_PASSWORD",
                User_age=row.Age,
                User_gender=row.Gender,
                User_weight=row.Weight_kg,
                User_Height=row.Height_cm / 100.0 if row.Height_cm > 3.0 else row.Height_cm,
                User_Allergies=row.Allergies,
                User_Dietary_Preferences=row.Dietary_Restrictions,
                User_Goals=row.Diet_Recommendation
            )
            db.add(user)
        else:
            user.User_age = row.Age
            user.User_gender = row.Gender
            user.User_weight = row.Weight_kg
            user.User_Height = row.Height_cm / 100.0 if row.Height_cm > 3.0 else row.Height_cm
            user.User_Allergies = row.Allergies
            user.User_Dietary_Preferences = row.Dietary_Restrictions
            user.User_Goals = row.Diet_Recommendation

        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
        ch.basic_ack(delivery_tag=method.delivery_tag)

def start():
    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    channel = connection.channel()
    channel.queue_declare(queue="diet_rec_queue", durable=True)
    channel.basic_qos(prefetch_count=10)
    channel.basic_consume(queue="diet_rec_queue", on_message_callback=process_message)
    channel.start_consuming()

if __name__ == "__main__":
    start()
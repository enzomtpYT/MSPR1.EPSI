import pika
import json
import os
import uuid
from datetime import datetime, timezone
from pydantic import ValidationError
from src.database import SessionLocal
from src.models.user import User
from src.models.workout_session import WorkoutSession
from src.models.biometrics_log import BiometricsLog
from src.etl.schemas import ExerciseRow

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

def process_message(ch, method, properties, body):
    try:
        data = json.loads(body)
        row = ExerciseRow(**data)
    except (ValidationError, json.JSONDecodeError):
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    db = SessionLocal()
    try:
        user_mail = f"tracker_{uuid.uuid4().hex[:8]}@etl.local"
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
        db.refresh(user)

        duration_minutes = int(row.Session_Duration * 60)
        today = datetime.now(timezone.utc).date()

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

        biometrics = BiometricsLog(
            User_ID=user.User_ID,
            Log_Date=today,
            Weight=row.Weight,
            Heart_Rate=row.Avg_BPM
        )
        db.add(biometrics)

        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
        ch.basic_ack(delivery_tag=method.delivery_tag)

def start():
    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    channel = connection.channel()
    channel.queue_declare(queue="exercise_queue", durable=True)
    channel.basic_qos(prefetch_count=10)
    channel.basic_consume(queue="exercise_queue", on_message_callback=process_message)
    channel.start_consuming()

if __name__ == "__main__":
    start()
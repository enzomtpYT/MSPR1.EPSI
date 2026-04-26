import multiprocessing
import logging
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from consumers import daily_food_consumer
from consumers import diet_rec_consumer
from consumers import exercise_consumer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_workers():
    logger.info("Initializing worker processes...")
    
    processes = [
        multiprocessing.Process(target=daily_food_consumer.start, name="DailyFoodWorker"),
        multiprocessing.Process(target=diet_rec_consumer.start, name="DietRecWorker"),
        multiprocessing.Process(target=exercise_consumer.start, name="ExerciseWorker")
    ]

    for p in processes:
        logger.info(f"Starting process: {p.name}")
        p.start()

    for p in processes:
        p.join()
        logger.warning(f"Process terminated: {p.name}")

if __name__ == "__main__":
    logger.info("Main worker script triggered.")
    run_workers()
import multiprocessing
import logging
from src.etl.consumers import daily_food_consumer
from src.etl.consumers import diet_rec_consumer
from src.etl.consumers import exercise_consumer

# Configure logging for the main worker script
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_workers():
    """
    Initializes and starts the consumer processes concurrently.
    Each consumer runs in its own process space listening to its designated queue.
    """
    logger.info("Initializing worker processes...")
    
    # Define the worker processes referencing their entry functions
    processes = [
        multiprocessing.Process(target=daily_food_consumer.start, name="DailyFoodWorker"),
        multiprocessing.Process(target=diet_rec_consumer.start, name="DietRecWorker"),
        multiprocessing.Process(target=exercise_consumer.start, name="ExerciseWorker")
    ]

    # Start all initialized processes
    for p in processes:
        logger.info(f"Starting process: {p.name}")
        p.start()

    # Wait for all processes to finish (blocks indefinitely since consumers run infinitely)
    for p in processes:
        p.join()
        logger.warning(f"Process terminated: {p.name}")

if __name__ == "__main__":
    logger.info("Main worker script triggered.")
    run_workers()
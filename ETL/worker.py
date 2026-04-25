import multiprocessing
from src.etl.consumers import daily_food_consumer
from src.etl.consumers import diet_rec_consumer
from src.etl.consumers import exercise_consumer

def run_workers():
    processes = [
        multiprocessing.Process(target=daily_food_consumer.start),
        multiprocessing.Process(target=diet_rec_consumer.start),
        multiprocessing.Process(target=exercise_consumer.start)
    ]

    for p in processes:
        p.start()

    for p in processes:
        p.join()

if __name__ == "__main__":
    run_workers()
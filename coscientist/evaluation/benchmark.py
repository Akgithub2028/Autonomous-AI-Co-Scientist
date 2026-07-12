import logging
import json
import os
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class BenchmarkDataset:
    """
    Interface for loading scientific discovery benchmark datasets from JSON.
    """
    def __init__(self, name: str, directory: str = "data/benchmarks"):
        self.name = name
        self.directory = directory
        self.tasks = []
        
    def load(self):
        """Load benchmark tasks from JSON files."""
        self.tasks = []
        if not os.path.exists(self.directory):
            logger.warning(f"Benchmark directory {self.directory} does not exist.")
            return

        for filename in os.listdir(self.directory):
            if filename.endswith(".json"):
                filepath = os.path.join(self.directory, filename)
                try:
                    with open(filepath, 'r') as f:
                        task = json.load(f)
                        self.tasks.append(task)
                except Exception as e:
                    logger.error(f"Failed to load benchmark task {filepath}: {e}")
        
        logger.info(f"Loaded {len(self.tasks)} benchmark tasks.")
        
    def get_tasks(self) -> List[Dict[str, Any]]:
        return self.tasks

class CoScientistBenchmarks(BenchmarkDataset):
    def __init__(self):
        super().__init__("CoScientistBenchmarks")
        
def get_benchmark(name: str) -> BenchmarkDataset:
    if name == "CoScientistBenchmarks":
        return CoScientistBenchmarks()
    else:
        raise ValueError(f"Unknown benchmark: {name}")

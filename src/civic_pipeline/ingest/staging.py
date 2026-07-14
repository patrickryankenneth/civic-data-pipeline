import sqlite3
import time
import json
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("staging")

class PipelineStaging:
    def __init__(self, db_path: str = "/ramdisk/pipeline_staging.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stage_metadata (
                    stage_name TEXT PRIMARY KEY,
                    execution_time_seconds REAL,
                    status TEXT,
                    timestamp DATETIME
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS local_vendors (
                    name TEXT PRIMARY KEY,
                    count INTEGER,
                    spend REAL
                )
            """)

    def record_stage(self, stage_name: str, duration: float, status: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO stage_metadata VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (stage_name, duration, status)
            )
            logger.info(f"Stage '{stage_name}' completed in {duration:.2f}s with status '{status}'")

    def run_with_timing(self, stage_name: str, func, *args, **kwargs):
        start = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            duration = time.perf_counter() - start
            self.record_stage(stage_name, duration, "SUCCESS")
            return result
        except Exception as e:
            duration = time.perf_counter() - start
            self.record_stage(stage_name, duration, f"FAILED: {str(e)}")
            raise e

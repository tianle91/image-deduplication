import logging
import os
from typing import Dict, List

from apscheduler.schedulers.base import BaseScheduler
from sqlitedict import SqliteDict

from image_dedup.convert import read_image
from image_dedup.phash import get_phash
from src.constants import PHASH_DB

logger = logging.getLogger(__name__)


def update_phash_in_db(path: str):
    with SqliteDict(PHASH_DB) as db:
        try:
            img = read_image(input_filename=path)
            db[path] = {
                "mtime": os.path.getmtime(path),
                "phash": get_phash(img=img) if img is not None else None,
            }
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to get phash for {path} with error {e}")


def update_phashes_in_db(paths: List[str], scheduler: BaseScheduler):
    with SqliteDict(PHASH_DB) as db:
        for p in paths:
            if p not in db or db[p]["mtime"] < os.path.getmtime(p):
                scheduler.add_job(
                    func=update_phash_in_db,
                    kwargs={"path": p},
                    misfire_grace_time=None,
                    max_instances=1,
                )


def get_phashes_from_db(paths: List[str]) -> Dict[str, str]:
    with SqliteDict(PHASH_DB) as db:
        return {
            p: db[p]["phash"] for p in paths if p in db and db[p]["phash"] is not None
        }

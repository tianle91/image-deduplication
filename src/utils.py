import logging
import multiprocessing
import os
import time
from glob import glob
from typing import Dict, List, Optional

import numpy as np
from apscheduler.schedulers.background import BackgroundScheduler
from sklearn.cluster import DBSCAN
from sqlitedict import SqliteDict

from image_dedup.convert import read_image
from image_dedup.phash import get_phash

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
scheduler.start()

CACHE_ROOT_DIR = os.getenv("CACHE_PATH", "/cache")
PHASH_DB = os.path.join(CACHE_ROOT_DIR, "phash.db")

INPUT_ROOT_DIR = os.getenv("INPUT_PATH", "/input")


def get_num_pending_jobs() -> int:
    return len(scheduler.get_jobs())


def get_input_paths() -> List[str]:
    return sorted(glob(os.path.join(INPUT_ROOT_DIR, "**", "*"), recursive=True))


def update_cache_with_phash(path: str):
    with SqliteDict(PHASH_DB) as db:
        try:
            img = read_image(input_filename=path)
            db[path] = get_phash(img=img) if img is not None else None
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to get phash for {path} with error {e}")


def update_cache_with_phashes(paths: List[str]):
    with SqliteDict(PHASH_DB) as db:
        for p in paths:
            if p not in db:
                scheduler.add_job(
                    func=update_cache_with_phash,
                    kwargs={"path": p},
                    misfire_grace_time=None,
                    max_instances=1,
                )


def get_phash_cached(path: str) -> Optional[str]:
    with SqliteDict(PHASH_DB) as db:
        return db.get(path, None)


def get_available_phashes(paths: List[str]) -> Dict[str, str]:
    with multiprocessing.Pool() as pool:
        phashes = pool.map(get_phash_cached, paths)
    return {p: phash for p, phash in zip(paths, phashes) if phash is not None}


def get_grouped_duplicates(paths: List[str], eps: float = 0.5) -> List[List[str]]:
    time_start = time.time()
    phashes = get_available_phashes(paths=paths)
    logger.warning(
        f"get_available_phashes took {time.time() - time_start:.2f} seconds."
    )
    if len(phashes) < len(paths):
        logger.warning(f"Missing {len(paths) - len(phashes)} files. ")
    if len(phashes) == 0:
        logger.warning("No phashes found! Try again later.")
        return [], time.time() - time_start
    else:
        available_paths = list(phashes.keys())
        X = np.array([[int(c, 16) for c in phash] for phash in phashes.values()])
        clustering = DBSCAN(eps=eps, min_samples=2, metric="hamming")
        clustering.fit(X)
        grouped_duplicates = {}
        for i, label in enumerate(clustering.labels_):
            if label > 0:
                existing_paths = grouped_duplicates.get(label, [])
                existing_paths.append(available_paths[i])
                grouped_duplicates[label] = existing_paths

        output = sorted(
            # most duplicates first
            [
                # shorter path first
                sorted(paths, key=lambda s: len(s))
                for paths in grouped_duplicates.values()
            ],
            key=lambda s: len(s),
            reverse=True,
        )
        return output, time.time() - time_start

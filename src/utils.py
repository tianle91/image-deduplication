import logging
import os
import time
from glob import glob
from typing import Dict, List

import numpy as np
import streamlit as st
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
                    misfire_grace_time=300,
                    max_instances=1,
                )


def get_available_phashes(paths: List[str]) -> Dict[str, str]:
    with SqliteDict(PHASH_DB) as db:
        return {p: db[p] for p in paths if p in db}


def get_grouped_duplicates(paths: List[str], eps: float = 0.5) -> List[List[str]]:
    time_start = time.time()
    phashes = get_available_phashes(paths=paths)
    phashes_vec = {
        p: [int(c, 16) for c in phash]
        for p, phash in phashes.items()
        if phash is not None
    }
    if len(phashes_vec) < len(paths):
        logger.warning(f"Missing {len(paths) - len(phashes_vec)} images. ")
    if len(phashes_vec) == 0:
        logger.warning("No phashes found! Try again later.")
        return [], time.time() - time_start
    else:
        available_paths = list(phashes_vec.keys())
        X = np.array(list(phashes_vec.values()))
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

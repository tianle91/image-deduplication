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
                )


def get_available_phashes(paths: List[str]) -> Dict[str, str]:
    with SqliteDict(PHASH_DB) as db:
        return {p: db[p] for p in paths if p in db}


def get_grouped_duplicates(paths: List[str], eps: float = 0.5) -> List[List[str]]:
    with st.spinner("Retrieving analysis results..."):
        time_start = time.time()
        phashes_vec = {
            p: [int(c, 16) for c in phash]
            for p, phash in get_available_phashes(paths=paths).items()
        }
        analysis_time = time.time() - time_start
        msg = f"Retrieving analysis took {analysis_time}. "
        if len(phashes_vec) < len(paths):
            msg += f"Missing {len(paths) - len(phashes_vec)} images. "
        logger.warning(msg)

    if len(phashes_vec) == 0:
        logger.warning("No phashes found! Try again later.")
        return []

    with st.spinner("Finding duplicates..."):
        time_start = time.time()
        paths = list(phashes_vec.keys())
        vecs = np.array(list(phashes_vec.values()))
        clustering = DBSCAN(eps=eps, min_samples=2, metric="hamming").fit(vecs)
        grouped_duplicates = {}
        for i, label in enumerate(clustering.labels_):
            if label > 0:
                grouped_duplicates[label] = grouped_duplicates.get(label, []) + [
                    paths[i]
                ]
        find_duplicates_time = time.time() - time_start
        logger.warning(f"Finding duplicates took {find_duplicates_time}")

    return [
        sorted(paths, key=lambda s: len(s)) for paths in grouped_duplicates.values()
    ]

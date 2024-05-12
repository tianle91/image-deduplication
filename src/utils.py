import logging
import multiprocessing
import os
import time
from glob import glob
from typing import List, Optional, Tuple

import numpy as np
import streamlit as st
from sklearn.cluster import DBSCAN
from sqlitedict import SqliteDict

from image_dedup.convert import read_image
from image_dedup.phash import get_phash

logger = logging.getLogger(__name__)


PHASH_DB = "phash.db"


def get_phash_cached(p: str) -> Optional[Tuple[str, bool]]:
    with SqliteDict(PHASH_DB) as db:
        if p not in db:
            try:
                db[p] = get_phash(img=read_image(p))
                db.commit()
            except Exception as e:
                return None
        return db[p]


def get_input_files(inputdir, ignorestrs):
    p = os.path.join(inputdir, "**", "*")
    with st.spinner(
        f'Finding files in `{p}` ignoring paths with {", ".join(ignorestrs)}...'
    ):
        input_files = sorted(glob(p, recursive=True))
        input_files = [
            s
            for s in input_files
            if all([ignorestr not in s for ignorestr in ignorestrs])
        ]
    return input_files


@st.cache_resource(show_spinner=False)
def get_grouped_duplicates(input_files: List[str], eps: float = 0.5) -> List[List[str]]:
    with st.spinner("Analyzing files..."):
        time_start = time.time()
        with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
            res_l = pool.map(get_phash_cached, input_files)

        phashes_vec = {
            p: [int(c, 16) for c in phash]
            for p, phash in zip(input_files, res_l)
            if phash is not None
        }
        analysis_time = time.time() - time_start
        logger.warning(f"Analysis took {analysis_time}")

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


def clean_up_and_stop_app():
    st.session_state["current_duplication_group"] = 0
    get_grouped_duplicates.clear()
    st.rerun()

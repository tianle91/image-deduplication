import logging
import multiprocessing
import os
import time
from glob import glob
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image
from sklearn.cluster import DBSCAN
from sqlitedict import SqliteDict

from image_dedup.convert import get_resized_image, read_image
from image_dedup.disjointset import get_grouped_duplicates
from image_dedup.phash import get_phash

logger = logging.getLogger(__name__)

PHASH_DB = "phash.db"
PAGE_SIZE = 10


def get_phash_and_analyzed_status(p: str) -> Optional[Tuple[str, bool]]:
    with SqliteDict(PHASH_DB) as db:
        if p not in db:
            try:
                phash = get_phash(img=read_image(p))
                db[p] = (phash, False)
                db.commit()
            except Exception as e:
                return None
        return db[p]


@st.cache_resource(show_spinner=False)
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
def get_grouped_duplicates(
    input_files: List[str], eps: float = 0.5
) -> Dict[int, List[str]]:
    with st.spinner("Analyzing files..."):
        time_start = time.time()
        with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
            res_l = pool.map(get_phash_and_analyzed_status, input_files)
        phashes = {}
        for p, res in zip(input_files, res_l):
            if res is None:
                continue
            phash, is_analyzed = res
            if not is_analyzed:
                phashes[p] = [int(c, 16) for c in phash]
        analysis_time = time.time() - time_start
        logger.warning(f"Analysis took {analysis_time}")

    with st.spinner("Finding duplicates..."):
        time_start = time.time()
        paths = list(phashes.keys())
        vecs = np.array(list(phashes.values()))
        clustering = DBSCAN(eps=eps, min_samples=2, metric="hamming").fit(vecs)
        grouped_duplicates = {}
        for i, label in enumerate(clustering.labels_):
            if label > 0:
                grouped_duplicates[label] = grouped_duplicates.get(label, []) + [
                    paths[i]
                ]
        find_duplicates_time = time.time() - time_start
        logger.warning(f"Finding duplicates took {find_duplicates_time}")

    return grouped_duplicates


def clean_up_and_stop_app():
    get_input_files.clear()
    get_grouped_duplicates.clear()
    st.stop()


input_files = []
with st.sidebar:
    st.title("Image Deduplication")
    inputdir = st.text_input(label="Input directory", value="/input").strip()
    ignorestrs = st.text_input(
        label="Ignore strings",
        value="@eaDir,",
        help="Separate strings with comma: `,`",
    )
    ignorestrs = [s.strip() for s in ignorestrs.split(",")]
    ignorestrs = [s for s in ignorestrs if len(s) > 0]
    input_files = get_input_files(inputdir=inputdir, ignorestrs=ignorestrs)
    st.write(f"Found {len(input_files)} files.")

    eps = st.slider(
        label="tolerance",
        min_value=0.1,
        max_value=0.9,
        value=0.5,
        help="increase tolerance to find more duplicates",
    )


DEDUPLICATION_README = """
# Deduplication

Uncheck the items you want to remove.
- [ ] This will be removed
- [x] This will not be removed
"""


@st.cache_resource(max_entries=1000)
def get_preview(p: str) -> Image.Image:
    return get_resized_image(img=read_image(p), max_length=200)


if len(input_files) > 0:
    grouped_duplicates = get_grouped_duplicates(input_files=input_files, eps=eps)
    num_groups = len(grouped_duplicates)

    with st.sidebar:
        st.write(f"Found {num_groups} grouped duplicates.")
        if len(grouped_duplicates) == 0:
            st.warning(
                "Expected to find duplicates? Try clearing cache and reload page."
            )
        if st.button("Clear cache"):
            os.remove(path=PHASH_DB)
            clean_up_and_stop_app()

    if len(grouped_duplicates) > 0:
        grouped_keys = list(grouped_duplicates.keys())
        grouped_keys_by_page = [
            grouped_keys[page_num : min(num_groups, page_num + PAGE_SIZE)]
            for page_num in range(0, num_groups, PAGE_SIZE)
        ]
        num_pages = len(grouped_keys_by_page)

        with st.sidebar:
            current_page = st.selectbox(
                label=f"Current page (out of {num_pages})",
                options=list(range(num_pages)),
            )

        st.markdown(DEDUPLICATION_README)
        with st.form("select photos to remove for current page"):
            original_files_to_remove = st.session_state.get(
                "original_files_to_remove", []
            )

            page_photo_checked = {}
            for i, k in enumerate(grouped_keys_by_page[current_page]):
                v = grouped_duplicates[k]
                with st.expander(f"{k}: {len(v)} duplicates", expanded=True):
                    for p in grouped_duplicates[k]:
                        size_in_mb = os.path.getsize(p) / (1024**2)
                        page_photo_checked[p] = st.checkbox(
                            label=f"Size: {size_in_mb:.2f} Mb",
                            value=p not in original_files_to_remove,
                            key=p,
                            help="Uncheck to delete",
                        )
                        st.image(image=get_preview(p), caption=p, width=400)

            if st.form_submit_button(label="Add to deletion list"):
                for p, checked in page_photo_checked.items():
                    if not checked and p not in original_files_to_remove:
                        original_files_to_remove.append(p)
                    elif p in original_files_to_remove:
                        original_files_to_remove.remove(p)
                st.session_state[
                    "original_files_to_remove"
                ] = original_files_to_remove.copy()

    # construct reversed mapping of grouped_duplicates so we can update analyzed status
    p_to_group = {}
    for group_dex, paths in grouped_duplicates.items():
        for p in paths:
            p_to_group[p] = group_dex

    with st.sidebar:
        original_files_to_remove = st.session_state.get("original_files_to_remove", [])
        st.write(f"Will be removing {len(original_files_to_remove)} files.")
        if st.button("Remove"):
            with st.spinner("Removing..."):
                groups_to_update_status = []
                progress_bar = st.progress(0.0)
                for i, remove_p in enumerate(original_files_to_remove):
                    progress_bar.progress(i / len(original_files_to_remove))
                    os.remove(path=remove_p)
                    groups_to_update_status.append(p_to_group[remove_p])

                # update groups with removed files as analyzed
                with SqliteDict(PHASH_DB) as db:
                    for group_dex in set(groups_to_update_status):
                        for p in grouped_duplicates[group_dex]:
                            phash, is_analyzed = db[p]
                            db[p] = (phash, True)
                            db.commit()

                progress_bar.empty()
            st.success(
                f"Removed {len(original_files_to_remove)} files! Reload to continue."
            )
            clean_up_and_stop_app()()

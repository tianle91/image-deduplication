import logging
import os
from glob import glob
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import streamlit as st
from sklearn.cluster import DBSCAN
from sqlitedict import SqliteDict

from image_dedup.convert import get_resized_image, read_image
from image_dedup.disjointset import get_grouped_duplicates
from image_dedup.phash import get_phash

logger = logging.getLogger(__name__)

PHASH_DB = "phash.db"
PAGE_SIZE = 10


def get_preview_and_phash(p: str) -> Tuple[np.ndarray, str]:
    img = read_image(p)
    if img is None:
        return (None, None)
    img = get_resized_image(img=img)
    return img, get_phash(img=img)


def get_preview_and_phash_cached(p: str) -> Tuple[np.ndarray, str]:
    with SqliteDict(PHASH_DB) as db:
        if p not in db:
            try:
                db[p] = get_preview_and_phash(p=p)
                db.commit()
            except Exception as e:
                return (None, None)
        return db[p]


@st.cache_resource(show_spinner=True)
def get_grouped_duplicates(input_files: List[str]) -> Dict[int, List[str]]:

    # generate phash
    phashes = {}
    progress_bar = st.progress(0.0, text='Analyzing images...')
    for i, p in enumerate(input_files):
        _, phash = get_preview_and_phash_cached(p)
        if phash is None:
            continue
        phashes[p] = [int(c, 16) for c in phash]
        progress_bar.progress(i / len(input_files))
    progress_bar.empty()

    # get grouped duplicates 
    paths = list(phashes.keys())
    vecs = np.array(list(phashes.values()))
    with st.spinner(text='Finding duplicates...'):
        clustering = DBSCAN(eps=0.5, min_samples=2, metric="hamming").fit(vecs)
    grouped_duplicates = {}
    for i, label in enumerate(clustering.labels_):
        if label > 0:
            grouped_duplicates[label] = grouped_duplicates.get(label, []) + [paths[i]]
    return grouped_duplicates


@st.cache_resource(show_spinner=True)
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


DEDUPLICATION_README = """
# Deduplication

Uncheck the items you want to remove.
- [ ] This will be removed
- [x] This will not be removed
"""


if len(input_files) > 0:
    with st.spinner("Finding duplicates"):
        grouped_duplicates = get_grouped_duplicates(input_files)
        num_groups = len(grouped_duplicates)
    st.write(f"Found {num_groups} grouped duplicates.")

    grouped_keys = list(grouped_duplicates.keys())
    grouped_keys_by_page = [
        grouped_keys[page_num : min(num_groups, page_num + PAGE_SIZE)]
        for page_num in range(0, num_groups, PAGE_SIZE)
    ]
    num_pages = len(grouped_keys_by_page)

    with st.sidebar:
        current_page = st.selectbox(
            label=f"Current page (out of {num_pages})", options=list(range(num_pages))
        )

    if len(grouped_duplicates) > 0:
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
                        page_photo_checked[p] = st.checkbox(
                            label=f"File: {p} Size: {os.path.getsize(p) / (1024**2):.2f} Mb",
                            value=p not in original_files_to_remove,
                        )
                        preview, phash = get_preview_and_phash_cached(p)
                        st.image(image=preview, caption=phash, width=400)

            if st.form_submit_button(label="Add to deletion list"):
                for p, checked in page_photo_checked.items():
                    if not checked and p not in original_files_to_remove:
                        original_files_to_remove.append(p)
                    elif p in original_files_to_remove:
                        original_files_to_remove.remove(p)
                st.session_state[
                    "original_files_to_remove"
                ] = original_files_to_remove.copy()

    with st.sidebar:
        original_files_to_remove = st.session_state.get("original_files_to_remove", [])
        st.write(f"Will be removing {len(original_files_to_remove)} files.")
        st.dataframe(pd.DataFrame({"to remove": original_files_to_remove}))
        if st.button("Remove"):
            with st.spinner("Removing..."):
                progress_bar = st.progress(0.0)
                for i, remove_p in enumerate(original_files_to_remove):
                    progress_bar.progress(i / len(original_files_to_remove))
                    os.remove(path=remove_p)
                progress_bar.empty()
            st.success(
                f"Removed {len(original_files_to_remove)} files! Reload to continue."
            )
            get_input_files.clear()
            st.stop()

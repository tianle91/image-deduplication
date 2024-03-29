import logging
import os
from glob import glob

import numpy as np
import pandas as pd
import streamlit as st
from imagededup.methods import PHash
from sqlitedict import SqliteDict

from convert import read_image
from disjointset import get_grouped_duplicates

logger = logging.getLogger(__name__)

TEMPDIR = "tempdir"
PHASH_CACHE_PATH = "phash_cache.db"
PHASHER = PHash()
PAGE_SIZE = 10


@st.cache_resource(max_entries=100000, show_spinner=False)
def read_image_and_resize(input_filename: str):
    resized_width = 400
    img = read_image(input_filename)
    if img is None:
        return None
    w, h = img.width, img.height
    proportional = min(resized_width / w, 1.0)
    resized_h = int(h * proportional)
    return img.resize((resized_width, resized_h))


def get_phash(input_filename: str):
    img = read_image_and_resize(input_filename)
    if img is None:
        return None
    image_array = np.array(img)
    if image_array.shape[2] > 3:
        logger.info(
            f"Reading {input_filename} "
            f"expecting (x, y, 3) but received {image_array.shape}. "
            "Taking slice [:,:,:3]."
        )
        image_array = image_array[:, :, :3]
    return PHASHER.encode_image(image_array=image_array)


@st.cache_resource(show_spinner=False)
def get_mappings_and_grouped_duplicates(input_files):
    # populate encodings
    encodings = {}
    progress_bar = st.progress(0.0)
    with SqliteDict(PHASH_CACHE_PATH) as db:
        for i, p in enumerate(input_files):
            if p not in db:
                db[p] = get_phash(p)
                db.commit()
            phash = db[p]
            if phash is not None:
                encodings[p] = phash
            progress_bar.progress(i / len(input_files))
    progress_bar.empty()
    # find grouped duplicates
    if len(encodings) == 0:
        return {}
    duplicates = PHASHER.find_duplicates(encoding_map=encodings)
    grouped_duplicates = get_grouped_duplicates(duplicates)
    return grouped_duplicates


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


with st.sidebar:
    st.title("Image Deduplication")
    inputdir = st.text_input(label="Input directory", value="/input")
    ignorestrs = st.text_input(
        label="Ignore strings",
        value="@eaDir,",
        help="Separate strings with comman: `,`",
    )
    ignorestrs = [s.strip() for s in ignorestrs.split(",")]
    ignorestrs = [s for s in ignorestrs if len(s) > 0]
    input_files = get_input_files(inputdir=inputdir, ignorestrs=ignorestrs)
    st.write(f"Found {len(input_files)} files.")
    with st.spinner("Finding duplicates"):
        grouped_duplicates = get_mappings_and_grouped_duplicates(input_files)
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


DEDUPLICATION_README = """
# Deduplication

Uncheck the items you want to remove.
- [ ] This will be removed
- [x] This will not be removed
"""


if len(grouped_duplicates) > 0:
    st.markdown(DEDUPLICATION_README)
    with st.form("select photos to remove for current page"):
        original_files_to_remove = st.session_state.get("original_files_to_remove", [])

        page_photo_checked = {}
        for i, k in enumerate(grouped_keys_by_page[current_page]):
            v = grouped_duplicates[k]
            with st.expander(f"{k}: {len(v)} duplicates", expanded=True):
                for p in grouped_duplicates[k]:
                    page_photo_checked[p] = st.checkbox(
                        label=f"File: {p} Size: {os.path.getsize(p) / (1024**2):.2f} Mb",
                        value=p not in original_files_to_remove,
                    )
                    st.image(image=read_image_and_resize(p), width=400)

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

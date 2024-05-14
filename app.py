import logging
import os
import time
from typing import List

import streamlit as st
from PIL import Image

from image_dedup.convert import get_resized_image, read_image
from src.utils import (
    INPUT_ROOT_DIR,
    get_grouped_duplicates,
    get_input_paths,
    get_num_pending_jobs,
    update_cache_with_phashes,
)

logger = logging.getLogger(__name__)


@st.cache_resource(ttl=3600, show_spinner=False)
def get_paths_and_update_cache():
    time_start = time.time()
    with st.spinner(f"Scanning for files in {INPUT_ROOT_DIR}..."):
        paths = get_input_paths()
        update_cache_with_phashes(paths=paths)
    time_end = time.time()
    time_taken = time_end - time_start
    print(f"Scanned {len(paths)} files in {time_taken:.2f} seconds.")
    return paths, time_taken


input_paths, input_paths_time_taken = get_paths_and_update_cache()
num_pending_jobs = get_num_pending_jobs()

with st.sidebar:
    st.write(
        f"Took {input_paths_time_taken:.2f} seconds to find {len(input_paths)} files in {INPUT_ROOT_DIR}."
    )
    if num_pending_jobs > 0:
        st.write(
            f"Pending analysis for {num_pending_jobs} ({100*num_pending_jobs/len(input_paths):.2f} pct) files."
        )
    eps = st.slider(
        label="tolerance",
        min_value=0.0,
        max_value=0.9,
        value=0.1,
        help="select 0 for exact duplicates, increase to find more duplicates",
    )


@st.cache_resource(max_entries=1000, show_spinner=False)
def get_preview(p: str) -> Image.Image:
    return get_resized_image(img=read_image(p), max_length=200)


def clean_up_and_stop_app():
    st.session_state["current_duplication_group"] = 0
    st.cache_resource.clear()
    st.rerun()


def show_duplication_results_and_add_to_deletion(paths: List[str]):
    MAX_FOLDERS_TO_SHOW = 5
    # print summary summary of paths
    folders = list({os.path.dirname(p) for p in paths})
    summary_text = f"Resolving {len(paths)} duplicates from {len(folders)} folders (uncheck to remove):\n"
    for folder in folders[:MAX_FOLDERS_TO_SHOW]:
        summary_text += f"- {folder}\n"
    if len(folders) > MAX_FOLDERS_TO_SHOW:
        summary_text += f"- ... and {len(folders) - MAX_FOLDERS_TO_SHOW} more folders\n"
        summary_text += f"Too many folders? Try decreasing tolerance (eps)."
    st.markdown(summary_text)

    with st.form("Add to deletion list"):
        original_files_to_remove = st.session_state.get("original_files_to_remove", [])
        paths_to_should_delete_mapping = {}
        for p in paths:
            size_in_mb = os.path.getsize(p) / (1024**2)
            paths_to_should_delete_mapping[p] = st.checkbox(
                label=f"Size: {size_in_mb:.2f} Mb",
                value=p not in original_files_to_remove,
                key=p,
                help="Uncheck to delete",
            )
            st.image(image=get_preview(p), caption=p, width=400)

        if st.form_submit_button(label="Add to deletion list"):
            # sync original_files_to_remove with paths_to_should_delete_mapping
            for p, checked in paths_to_should_delete_mapping.items():
                if not checked and p not in original_files_to_remove:
                    original_files_to_remove.append(p)
                elif p in original_files_to_remove:
                    original_files_to_remove.remove(p)
            st.session_state[
                "original_files_to_remove"
            ] = original_files_to_remove.copy()
            # advance current_duplication_group if possible
            if not (current_duplication_group + 1 > len(grouped_duplicates) - 1):
                st.session_state["current_duplication_group"] = (
                    current_duplication_group + 1
                )
                st.rerun()
            else:
                st.success("Done! See sidebar for removal confirmation.")


if len(input_paths) > 0:
    grouped_duplicates, grouped_duplicates_time_taken = st.cache_resource(
        get_grouped_duplicates, max_entries=1, show_spinner=False
    )(paths=input_paths, eps=eps)
    with st.sidebar:
        st.write(
            f"Took {grouped_duplicates_time_taken:.2f} seconds to find {len(grouped_duplicates)} grouped duplicates."
        )
        if st.checkbox("Ignore duplicates within the same folder"):
            grouped_duplicates = list(
                filter(
                    lambda paths: len({os.path.dirname(p) for p in paths}) > 1,
                    grouped_duplicates,
                )
            )
        if len(grouped_duplicates) == 0:
            st.warning(
                "Expected to find duplicates? Come back later or try resetting the page."
            )
        if st.button("Reset"):
            clean_up_and_stop_app()

    if len(grouped_duplicates) > 0:
        current_duplication_group = st.session_state.get("current_duplication_group", 0)
        st.markdown(
            f"Viewing Duplication Group: {current_duplication_group} / {len(grouped_duplicates)}"
        )

        l_col, r_col = st.columns(2)
        with l_col:
            if st.button(
                f"Go to {current_duplication_group - 1}",
                disabled=current_duplication_group - 1 < 0,
            ):
                st.session_state["current_duplication_group"] = (
                    current_duplication_group - 1
                )
                st.rerun()
        with r_col:
            if st.button(
                f"Go to {current_duplication_group + 1}",
                disabled=current_duplication_group + 1 > len(grouped_duplicates) - 1,
            ):
                st.session_state["current_duplication_group"] = (
                    current_duplication_group + 1
                )
                st.rerun()
        # using st.rerun() above avoids current_duplication_group being desynced due to lazy updates
        show_duplication_results_and_add_to_deletion(
            paths=grouped_duplicates[current_duplication_group]
        )

    with st.sidebar:
        original_files_to_remove = st.session_state.get("original_files_to_remove", [])
        st.warning(f"Will be removing {len(original_files_to_remove)} files.")
        if st.button("Remove", disabled=len(original_files_to_remove) == 0):
            with st.spinner("Removing..."):
                progress_bar = st.progress(0.0)
                for i, remove_p in enumerate(original_files_to_remove):
                    progress_bar.progress(i / len(original_files_to_remove))
                    os.remove(path=remove_p)
                progress_bar.empty()
            st.success(
                f"Removed {len(original_files_to_remove)} files! Reload to continue."
            )
            clean_up_and_stop_app()

import logging
import os
from typing import List

import streamlit as st
from apscheduler.schedulers.background import BackgroundScheduler
from PIL import Image

from image_dedup.convert import get_resized_image, read_image
from src import get_grouped_duplicates
from src.constants import INPUT_ROOT_DIR
from src.paths import get_paths_from_db, update_paths_in_db
from src.phash import get_phashes_from_db, update_phashes_in_db

logger = logging.getLogger(__name__)

# manage background tasks
scheduler = BackgroundScheduler()
scheduler.start()
scheduler.add_job(
    func=update_paths_in_db,
    trigger="interval",
    minutes=10,
    misfire_grace_time=None,
    max_instances=1,
)


################ GET INPUT PATHS ################


@st.cache_resource(max_entries=1, show_spinner=False)
def get_paths_from_db_cached() -> List[str]:
    paths = get_paths_from_db()
    update_phashes_in_db(paths=paths, scheduler=scheduler)
    return paths


input_paths = get_paths_from_db_cached()
with st.sidebar:
    st.write(f"Found {len(input_paths)} files in `{INPUT_ROOT_DIR}`")
    eps = st.slider(
        label="tolerance",
        min_value=0.0,
        max_value=0.9,
        value=0.1,
        help="select 0 for exact duplicates, increase to find more duplicates",
    )


################ GET PHASHES ################


def rescan_files_and_reset_all():
    st.session_state["current_duplication_group"] = 0
    st.cache_resource.clear()
    st.rerun()


@st.cache_resource(max_entries=1, show_spinner=False)
def get_phashes_from_db_cached(paths):
    return get_phashes_from_db(paths=paths)


phashes = get_phashes_from_db_cached(paths=input_paths)
with st.sidebar:
    num_files_without_phash = len(input_paths) - len(phashes)
    if num_files_without_phash > 0:
        st.warning(
            f"Found {num_files_without_phash} ({100*num_files_without_phash/len(input_paths):.2f} pct) files without phash. "
            "Try refreshing analysis later."
        )
    l_col, r_col = st.columns(2)
    with l_col:
        if st.button(
            "Refresh analysis",
            help="Reloads analysis results which are running in the background.",
        ):
            get_phashes_from_db_cached.clear()
    with r_col:
        if st.button(
            "Rescan files",
            help="Rescan files and clears all analysis results (this might take a while).",
        ):
            rescan_files_and_reset_all()


################ SHOW SINGLE DUPLICATE GROUP ################


@st.cache_resource(max_entries=1000, show_spinner=False)
def get_preview(p: str) -> Image.Image:
    return get_resized_image(img=read_image(p), max_length=200)


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


################ SHOW ALL DUPLICATES ################


@st.cache_resource(max_entries=1, show_spinner=False)
def get_grouped_duplicates_cached(**kwargs):
    return get_grouped_duplicates(**kwargs)


if len(phashes) > 0:
    with st.spinner("Finding duplicates..."):
        grouped_duplicates = get_grouped_duplicates_cached(phashes=phashes, eps=eps)
    with st.sidebar:
        st.write(f"Found {len(grouped_duplicates)} grouped duplicates.")
        if st.checkbox("Ignore duplicates within the same folder"):
            grouped_duplicates = list(
                filter(
                    lambda paths: len({os.path.dirname(p) for p in paths}) > 1,
                    grouped_duplicates,
                )
            )
        if len(grouped_duplicates) == 0:
            st.warning("Expected to find duplicates? Try refreshing analysis.")

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
            rescan_files_and_reset_all()

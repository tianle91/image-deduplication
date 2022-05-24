import os
from glob import glob

import numpy as np
import streamlit as st
from imagededup.methods import PHash
from sqlitedict import SqliteDict

from convert import read_image
from disjointset import get_grouped_duplicates

tempdir = 'tempdir'
phash_cache_path = 'phash_cache.db'
phasher = PHash()


@st.cache(max_entries=1000000)
def read_image_and_resize(input_filename: str):
    resized_width = 400
    img = read_image(input_filename)
    w, h = img.width, img.height
    proportional = min(resized_width / w, 1.)
    resized_h = int(h * proportional)
    return img.resize((resized_width, resized_h))


def get_phash(input_filename: str):
    img = read_image_and_resize(input_filename)
    if img is None:
        return None
    else:
        return phasher.encode_image(image_array=np.array(img))


@st.cache(show_spinner=False, suppress_st_warning=True)
def get_mappings_and_grouped_duplicates(input_files):
    # populate encodings
    encodings = {}
    progress_bar = st.progress(0.)
    db = SqliteDict(phash_cache_path)
    for i, p in enumerate(input_files):
        if p not in db:
            db[p] = get_phash(p)
            db.commit()
        phash = db[p]
        if phash is not None:
            encodings[p] = phash
        progress_bar.progress(i / len(input_files))
    db.close()
    progress_bar.empty()

    if len(encodings) > 0:
        # find duplicates, this should be fast
        duplicates = phasher.find_duplicates(encoding_map=encodings)
        grouped_duplicates = get_grouped_duplicates(duplicates)
        return grouped_duplicates
    return {}


with st.sidebar:
    st.title('Image Deduplication')
    inputdir = st.text_input(label='Input directory', value='/input')
    input_files = sorted(glob(os.path.join(inputdir, '*')))
    st.write(f'Found {len(input_files)} files')
    with st.spinner('Finding duplicates'):
        grouped_duplicates = get_mappings_and_grouped_duplicates(input_files)
        num_groups = len(grouped_duplicates)
    st.write(f'Found {num_groups} grouped duplicates.')

    page_size = 10
    grouped_keys = list(grouped_duplicates.keys())
    grouped_keys_by_page = [
        grouped_keys[page_num:min(num_groups, page_num + page_size)]
        for page_num in range(0, num_groups, page_size)
    ]
    current_page = st.selectbox(
        label='Current page',
        options=list(range(len(grouped_keys_by_page)))
    )


deduplication_readme = '''
# Deduplication

Uncheck the items you want to remove.
- [ ] This will be removed
- [x] This will not be removed
'''
if len(grouped_duplicates) > 0:
    st.markdown(deduplication_readme)
    original_files_to_remove = []

    with st.form('select photos to remove for current page'):
        page_photo_checked = {}
        for i, k in enumerate(grouped_keys_by_page[current_page]):
            v = grouped_duplicates[k]
            with st.expander(f'{k}: {len(v)} duplicates'):
                for p in grouped_duplicates[k]:
                    page_photo_checked[p] = st.checkbox(label=p, value=True)
                    st.image(image=read_image_and_resize(p), width=400)
        if st.form_submit_button(label='Add to deletion list'):
            for p, checked in page_photo_checked.items():
                if not checked and p not in original_files_to_remove:
                    original_files_to_remove.append(p)
                elif p in original_files_to_remove:
                    original_files_to_remove.remove(p)


with st.sidebar:
    st.write(f'Will be removing {len(original_files_to_remove)} files.')
    if st.button('Remove'):
        for i, remove_p in enumerate(original_files_to_remove):
            st.write(f'[{i}/{len(original_files_to_remove)}] {remove_p}')
            os.remove(path=remove_p)
        st.success(f'Removed {len(original_files_to_remove)} files!')

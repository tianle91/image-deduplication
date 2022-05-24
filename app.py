import os
from glob import glob

import streamlit as st
from imagededup.methods import PHash
from sqlitedict import SqliteDict

from convert import read_image_as_array
from disjointset import get_grouped_duplicates

tempdir = 'tempdir'
phash_cache_path = 'phash_cache.db'
phasher = PHash()


def get_phash(input_filename: str):
    image_array = read_image_as_array(input_filename)
    if image_array is None:
        return None
    else:
        return phasher.encode_image(image_array=image_array)


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
    inputdir = st.text_input(label='Input directory', value='inputdir')
    input_files = sorted(glob(os.path.join(inputdir, '*')))
    st.write(f'Found {len(input_files)} files')
    with st.spinner('Finding duplicates'):
        grouped_duplicates = get_mappings_and_grouped_duplicates(input_files)
    st.write(f'Found {len(grouped_duplicates)} grouped duplicates.')


if len(grouped_duplicates) > 0:
    st.header('Deduplication')
    st.markdown('''
    Uncheck the items you want to remove.
    - [ ] This will be removed
    - [x] This will not be removed
    ''')
    with st.form('Deduplication'):
        remove_original_files = []

        for i, k in enumerate(grouped_duplicates):
            v = grouped_duplicates[k]
            with st.expander(f'{k}: {len(v)} duplicates'):
                for p in v:
                    if not st.checkbox(label=p, value=True):
                        remove_original_files.append(p)
                    st.image(image=read_image_as_array(p), width=400)
            break
        if st.form_submit_button():
            st.write(f'Removing {len(remove_original_files)} files.')
            for i, remove_p in enumerate(remove_original_files):
                st.write(f'[{i}/{len(remove_original_files)}] {remove_p}')
                os.remove(path=remove_p)
            st.success(f'Removed {len(remove_original_files)} files!')

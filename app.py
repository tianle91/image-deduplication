import os
from glob import glob

import streamlit as st
from imagededup.methods import PHash

from convert import read_image_as_array
from disjointset import get_grouped_duplicates

tempdir = 'tempdir'
phasher = PHash()

st.title('Image Deduplication')

inputdir = st.text_input(label='Input directory', value='inputdir')
input_files = glob(os.path.join(inputdir, '*'))
st.write(f'Found {len(input_files)} files')


@st.cache(show_spinner=False, persist=True)
def get_phash(input_filename: str):
    image_array = read_image_as_array(input_filename)
    if image_array is None:
        return None
    else:
        return phasher.encode_image(image_array=image_array)


@st.cache(show_spinner=False, persist=True, suppress_st_warning=True)
def get_mappings_and_grouped_duplicates(input_files):
    # populate encodings
    encodings = {}
    progress_bar = st.progress(0.)
    for i, p in enumerate(input_files):
        encodings[p] = get_phash(p)
        progress_bar.progress(i / len(input_files))
    progress_bar.empty()
    # find duplicates, this should be fast
    duplicates = phasher.find_duplicates(encoding_map=encodings)
    grouped_duplicates = get_grouped_duplicates(duplicates)
    return grouped_duplicates


if len(input_files) > 0:

    grouped_duplicates = get_mappings_and_grouped_duplicates(input_files)

    st.header('Deduplication')
    if len(grouped_duplicates) == 0:
        st.success('No duplicates found!')
    else:
        with st.form('Deduplication'):
            st.text('Uncheck the items you want to remove.')
            remove_original_files = []
            for k, v in grouped_duplicates.items():
                with st.expander(f'{k}: {len(v)} duplicates'):
                    for p in v:
                        if not st.checkbox(label=p, value=True):
                            remove_original_files.append(p)
                        st.image(image=read_image_as_array(p), width=400)
            if st.form_submit_button():
                st.write(f'Removing {len(remove_original_files)} files.')
                for i, remove_p in enumerate(remove_original_files):
                    st.write(f'[{i}/{len(remove_original_files)}] {remove_p}')
                    os.remove(path=remove_p)
                st.success(f'Removed {len(remove_original_files)} files!')

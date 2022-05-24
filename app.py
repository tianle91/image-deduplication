import os
from glob import glob

import streamlit as st
from imagededup.methods import PHash

from convert import convert_inputs
from disjointset import get_grouped_duplicates

inputdir = 'inputdir'
tempdir = 'tempdir'
phasher = PHash()


input_files = glob(os.path.join(inputdir, '*'))


@st.cache(show_spinner=True, max_entries=1, suppress_st_warning=True)
def get_mappings_and_grouped_duplicates(input_files, inputdir, tempdir):
    # input_files is here to serve as a checksum for items in inputdir
    filename_to_path_mapping = convert_inputs(input_directory=inputdir, tempdir=tempdir)
    encodings = phasher.encode_images(tempdir)
    duplicates = phasher.find_duplicates(encoding_map=encodings)
    grouped_duplicates = get_grouped_duplicates(duplicates)
    return filename_to_path_mapping, grouped_duplicates


filename_to_path_mapping, grouped_duplicates = get_mappings_and_grouped_duplicates(
    input_files, inputdir, tempdir)


with st.form('Deduplication'):
    remove_original_files = []
    for k, v in grouped_duplicates.items():
        with st.expander(f'{k}: {len(v)} duplicates'):
            for p in v:
                original_filename, output_filename = filename_to_path_mapping[p]
                if not st.checkbox(label=original_filename, value=True):
                    remove_original_files.append(original_filename)
                st.image(image=output_filename, width=400)
    if st.form_submit_button():
        for i, remove_p in enumerate(remove_original_files):
            st.write(f'[{i}/{len(remove_original_files)}] {remove_p}')
            os.remove(path=remove_p)

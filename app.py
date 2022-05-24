import os
from glob import glob

import streamlit as st
from imagededup.methods import PHash

from convert import convert_inputs
from disjointset import get_grouped_duplicates

tempdir = 'tempdir'
phasher = PHash()

st.title('Image Deduplication')

inputdir = st.text_input(label='Input directory', value='inputdir')
input_files = glob(os.path.join(inputdir, '*'))
print('\n'.join(input_files[:5]))


@st.cache(show_spinner=True, max_entries=1, suppress_st_warning=True)
def get_mappings_and_grouped_duplicates(input_files, inputdir, tempdir):
    # input_files is here to serve as a checksum for items in inputdir
    filename_to_path_mapping = convert_inputs(input_directory=inputdir, tempdir=tempdir)
    encodings = phasher.encode_images(tempdir)
    duplicates = phasher.find_duplicates(encoding_map=encodings)
    grouped_duplicates = get_grouped_duplicates(duplicates)
    return filename_to_path_mapping, grouped_duplicates


if len(input_files) > 0:
    
    filename_to_path_mapping, grouped_duplicates = get_mappings_and_grouped_duplicates(
        input_files, inputdir, tempdir)

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
                        original_filename, output_filename = filename_to_path_mapping[p]
                        if not st.checkbox(label=original_filename, value=True):
                            remove_original_files.append(original_filename)
                        st.image(image=output_filename, width=400)
            if st.form_submit_button():
                for i, remove_p in enumerate(remove_original_files):
                    st.write(f'[{i}/{len(remove_original_files)}] {remove_p}')
                    os.remove(path=remove_p)
                st.success(f'Removed {len(remove_original_files)} files!')

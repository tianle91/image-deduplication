import os
import shutil
from glob import glob
from pathlib import Path
from typing import Dict, Tuple

import pyheif
import streamlit as st
from PIL import Image


def dump_input_heic_as_jpg(input_path, output_path):
    heif_file = pyheif.read(input_path)
    image = Image.frombytes(
        heif_file.mode,
        heif_file.size,
        heif_file.data,
        "raw",
        heif_file.mode,
        heif_file.stride,
    )
    image.save(output_path, "JPEG")


def convert_inputs(input_directory: str, tempdir: str = 'tempdir') -> Dict[str, Tuple[str, str]]:

    shutil.rmtree(tempdir)
    os.makedirs(tempdir)
    filename_to_path_mapping = {}

    files = glob(os.path.join(input_directory, '*'))
    progress_bar = st.progress(0.)

    for i, input_path in enumerate(files):

        filename = Path(input_path).name
        filename_extension = filename.split('.')[1].lower()
        output_filename = filename.split('.')[0] + '.jpg'
        output_path = os.path.join(tempdir, output_filename)

        if filename_extension == 'heic':
            dump_input_heic_as_jpg(input_path, output_path)
        elif filename_extension == 'jpg':
            shutil.copyfile(input_path, output_path)
        else:
            print(f'Ignoring {input_path}')
            continue

        filename_to_path_mapping[output_filename] = (input_path, output_path)
        progress_bar.progress(i / len(files))

    progress_bar.empty()
    return filename_to_path_mapping

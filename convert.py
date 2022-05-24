from pathlib import Path

import numpy as np
import pyheif
from PIL import Image


def read_image_as_array(input_filename):
    filename = Path(input_filename).name
    filename_split = filename.split('.')
    if len(filename_split) != 2:
        return None
    else:
        filename_extension = filename.split('.')[1].lower()
        if filename_extension == 'heic':
            heif_file = pyheif.read(input_filename)
            image = Image.frombytes(
                heif_file.mode,
                heif_file.size,
                heif_file.data,
                "raw",
                heif_file.mode,
                heif_file.stride,
            )
        else:
            try:
                image = Image.open(input_filename)
            except Exception:
                return None
        return np.array(image)

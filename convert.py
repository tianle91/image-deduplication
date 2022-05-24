from pathlib import Path

import pyheif
from PIL import Image


def read_image(input_filename) -> Image.Image:
    filename = Path(input_filename).name
    filename_split = filename.split('.')
    if len(filename_split) != 2:
        print(f'Ignoring {input_filename} because it has no extension.')
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
        elif filename_extension in ('mov', 'mp4'):
            print(f'Ignoring {input_filename} because it is a video.')
            return None
        else:
            try:
                image = Image.open(input_filename)
            except Exception:
                print(f'Ignoring {input_filename} because it cannot be openend.')
                return None
        return image

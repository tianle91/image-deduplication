import logging
import os
from pathlib import Path
from typing import Optional

import pyheif
from PIL import Image

logger = logging.getLogger(__name__)

def read_heic_image(input_filename: str) -> Image.Image:
    heif_file = pyheif.read(input_filename)
    image = Image.frombytes(
        heif_file.mode,
        heif_file.size,
        heif_file.data,
        "raw",
        heif_file.mode,
        heif_file.stride,
    )
    return image


def read_image(input_filename: str) -> Optional[Image.Image]:
    filename = Path(input_filename).name
    if not os.path.isfile(path=input_filename):
        return None

    filename_split = filename.split(".")
    if len(filename_split) != 2:
        logger.info(f"Ignoring {input_filename} because it has no extension.")
        return None

    filename_extension = filename.split(".")[1].lower()
    if filename_extension in ("mov", "mp4"):
        logger.info(f"Ignoring {input_filename} because it is a video.")
        return None
    # maybe it's an image at this point
    if filename_extension == "heic":
        return read_heic_image(input_filename=input_filename)
    else:
        try:
            image = Image.open(input_filename)
            return image
        except Exception:
            logger.warning(f"Ignoring {input_filename} because it cannot be opened.")


def get_resized_image(img: Image.Image, max_length = 400) -> Image.Image:
    w, h = img.size
    max_w_h = max(w, h)
    if max_w_h < max_length:
        return img
    elif w == max_w_h:
        # shrink w to max_length
        scale = max_length / w
        return img.resize(size=(max_length, int(scale * h)))
    else:
        # shrink h to max_length
        scale = max_length / h
        return img.resize(size=(int(scale * w), max_length))

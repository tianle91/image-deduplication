import logging
import os
from pathlib import Path
from typing import Optional

import cv2 as cv
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


def extract_mid_video_frame(input_filename: str) -> Image.Image:
    cap = cv.VideoCapture(input_filename)
    _, image = cap.read()
    image_rgb = cv.cvtColor(image, cv.COLOR_BGR2RGB)
    output = Image.fromarray(image_rgb)
    cap.release()
    return output


def read_image(input_filename: str) -> Optional[Image.Image]:
    filename = Path(input_filename).name
    if not os.path.isfile(path=input_filename):
        return None

    filename_split = filename.split(".")
    if len(filename_split) != 2:
        logger.info(f"Ignoring {input_filename} because it has no extension.")
        return None

    filename_extension = filename.split(".")[1].lower()
    if filename_extension in ("mov", "mp4", "mkv", "avi"):
        try:
            image = extract_mid_video_frame(input_filename=input_filename)
            return image
        except Exception as e:
            logger.warning(
                f"Failed to open video with cv2: {input_filename} with error {e}"
            )
    else:
        # Try to open image with pillow
        if filename_extension == "heic":
            return read_heic_image(input_filename=input_filename)
        try:
            image = Image.open(input_filename)
            return image
        except Exception as e:
            logger.warning(
                f"Failed to open image with pillow: {input_filename} with error {e}"
            )


def get_resized_image(img: Image.Image, max_length=400) -> Image.Image:
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

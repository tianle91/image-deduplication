import logging
import os
from pathlib import Path
from typing import Optional

import cv2 as cv
import pyheif
from PIL import Image

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = ["mov", "mp4", "mkv", "avi"]
IMAGE_EXTENSIONS = ["heic", "jpg", "png", "webp", "gif", "jpeg"]


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

    # Get the total number of frames
    length = int(cap.get(cv.CAP_PROP_FRAME_COUNT))
    half_point = length // 2  # Approximately half if number of frames are odd
    # Set the reader to the given frame number (half_point)
    cap.set(cv.CAP_PROP_POS_FRAMES, half_point)

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
    if filename_extension in VIDEO_EXTENSIONS:
        try:
            image = extract_mid_video_frame(input_filename=input_filename)
            return image
        except Exception as e:
            logger.warning(
                f"Failed to open video with cv2: {input_filename} with error {e}"
            )
    elif filename_extension in IMAGE_EXTENSIONS:
        try:
            if filename_extension == "heic":
                return read_heic_image(input_filename=input_filename)
            else:
                return Image.open(input_filename)
        except Exception as e:
            logger.warning(
                f"Failed to open image with pillow: {input_filename} with error {e}"
            )
    else:
        logger.warning(f"Ignoring {input_filename} with extension {filename_extension}")


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

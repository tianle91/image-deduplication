import numpy as np
from PIL import Image
from scipy.fftpack import dct


def get_phash(img: Image.Image) -> str:
    img = img.resize(size=(32, 32), resample=Image.NEAREST).convert("L")
    img_arr = np.array(img).astype("uint8")
    dct_arr = dct(dct(img_arr, axis=0), axis=1)[:8, :8]
    dct_median = np.median(np.ndarray.flatten(dct_arr)[1:])
    phash_arr = dct_arr < dct_median
    return "".join("%0.2x" % x for x in np.packbits(phash_arr))

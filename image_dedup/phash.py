import numpy as np
from PIL import Image

HASH_WIDTH = 8

def get_phash(img: Image.Image) -> str:
    img = img.resize(size=(HASH_WIDTH, HASH_WIDTH), resample=Image.NEAREST)
    img_arr = np.array(img).astype("uint8")
    medians = np.tile(np.median(img_arr, axis=[0, 1]).astype("uint8"), reps=(HASH_WIDTH, HASH_WIDTH, 1))
    hash_arr = img_arr < medians
    return "".join("%0.2x" % x for x in np.packbits(hash_arr.flatten()))

if __name__ == '__main__':
    print(get_phash(Image.open('sampledir/AB780CA7-DAFB-49BA-A4EC-5E93AAC57381_4_5005_c.jpeg')))

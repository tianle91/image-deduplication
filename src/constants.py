import os

CACHE_ROOT_DIR = os.getenv("CACHE_PATH", "/cache")
PHASH_DB = os.path.join(CACHE_ROOT_DIR, "phash.db")
PATHS_DB = os.path.join(CACHE_ROOT_DIR, "paths.db")

INPUT_ROOT_DIR = os.getenv("INPUT_PATH", "/input")

import os
from glob import glob
from typing import List

from sqlitedict import SqliteDict

from src.constants import INPUT_ROOT_DIR, PATHS_DB


def get_input_paths() -> List[str]:
    return sorted(glob(os.path.join(INPUT_ROOT_DIR, "**", "*"), recursive=True))


def update_paths_in_db():
    with SqliteDict(PATHS_DB) as db:
        db[0] = get_input_paths()
        db.commit()


def get_paths_from_db() -> List[str]:
    with SqliteDict(PATHS_DB) as db:
        if 0 not in db:
            return get_input_paths()
        else:
            return db[0]

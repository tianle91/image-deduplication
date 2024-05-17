from typing import Dict, List

import numpy as np
from sklearn.cluster import DBSCAN


def get_grouped_duplicates(
    phashes: Dict[str, str], eps: float = 0.5
) -> List[List[str]]:
    if len(phashes) == 0:
        return []

    available_paths = list(phashes.keys())
    X = np.array([[int(c, 16) for c in phash] for phash in phashes.values()])
    clustering = DBSCAN(eps=eps, min_samples=2, metric="hamming", n_jobs=-1)
    clustering.fit(X)
    grouped_duplicates = {}
    for i, label in enumerate(clustering.labels_):
        if label > 0:
            existing_paths = grouped_duplicates.get(label, [])
            existing_paths.append(available_paths[i])
            grouped_duplicates[label] = existing_paths

    output = sorted(
        # most duplicates first
        [
            # shorter path first
            sorted(paths, key=lambda s: len(s))
            for paths in grouped_duplicates.values()
        ],
        key=lambda s: len(s),
        reverse=True,
    )
    return output

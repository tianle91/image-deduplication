from typing import Dict, List


# A class to represent a disjoint set
class DisjointSet:
    parent = {}

    # stores the depth of trees
    rank = {}

    # perform MakeSet operation
    def makeSet(self, universe):
        # create `n` disjoint sets (one for each item)
        for i in universe:
            self.parent[i] = i
            self.rank[i] = 0

    # Find the root of the set in which element `k` belongs
    def Find(self, k):
        # if `k` is not the root
        if self.parent[k] != k:
            # path compression
            self.parent[k] = self.Find(self.parent[k])
        return self.parent[k]

    # Perform Union of two subsets
    def Union(self, a, b):
        # find the root of the sets in which elements `x` and `y` belongs
        x = self.Find(a)
        y = self.Find(b)

        # if `x` and `y` are present in the same set
        if x == y:
            return

        # Always attach a smaller depth tree under the root of the deeper tree.
        if self.rank[x] > self.rank[y]:
            self.parent[y] = x
        elif self.rank[x] < self.rank[y]:
            self.parent[x] = y
        else:
            self.parent[x] = y
            self.rank[y] = self.rank[y] + 1


def get_grouped_duplicates(duplicates: Dict[str, List[str]]) -> Dict[str, List[str]]:
    djs = DisjointSet()
    djs.makeSet(duplicates.keys())
    for k, vs in duplicates.items():
        for v in vs:
            djs.Union(k, v)

    grouped_duplicates = {}
    for k in duplicates:
        parent_k = djs.Find(k)
        parent_duplicates = grouped_duplicates.get(parent_k, [])
        parent_duplicates.append(k)
        grouped_duplicates[parent_k] = parent_duplicates

    grouped_duplicates = {
        k: v
        for k, v in grouped_duplicates.items()
        if len(v) > 1
    }
    return grouped_duplicates

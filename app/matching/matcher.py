import heapq
from itertools import count

from matching.match_score import MatchScore


class ItemMatcher:
    def __init__(self, max_size = 10):
        if max_size <= 0:
            raise ValueError("max_size of item match list must be > 0")

        self.max_size = max_size
        self._heap: list[tuple[float, int, MatchScore]] = [] # heapq has smallest element at 0, and insertion/deletion faster than a list
        self._count = count() # counter ensures ordering is deterministic

    def add(self, match: MatchScore) -> None:
        score = match.score

        # simply fill heap if under max size
        if len(self._heap) < self.max_size:
            heapq.heappush(
                self._heap, (score, next(self._count), match)
            )

        # once full, only keep the highest scores
        # if a newer item ties the score, replace it (this prioritizes newer items from the DB)
        elif score >= self._heap[0][0]:
            heapq.heapreplace(
                self._heap, (score, next(self._count), match)
            )

# TODO implement
    # def get_sorted(self) -> list[MatchScore]:
    #     """Return retained objects in descending score order."""
    #     return [
    #         MatchScore(score=score) for score, count, obj in sorted(
    #             self._heap, key=lambda item: item[0], reverse=True
    #         )
    #     ]

    def __len__(self):
        return len(self._heap)

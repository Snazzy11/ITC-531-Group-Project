import heapq
from itertools import count

from database import models
from sqlalchemy.orm import Session

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

    def get_sorted(self) -> list[MatchScore]:
        """Return retained objects in descending score order."""
        return [
            match_score for score, count, match_score in sorted(
                self._heap, key=lambda item: item[0], reverse=True
            )
        ]

    def __len__(self):
        return len(self._heap)

def calculate_match_score(item: models.Item, candidate: models.Item) -> MatchScore:
    item_words = item.description.lower().strip().split()
    candidate_words = candidate.description.lower().strip().split()

    already_matched_words: set[str] = set()

    score = 0.0
    for w in item_words:
        if w in candidate_words:
            if w in already_matched_words:
                score += 0.1
            else:
                score += 0.25
                already_matched_words.add(w)
    return MatchScore(score=score, item_id=item.id, candidate_item_id=candidate.id)


async def get_potential_matches(db: Session, item_id: int, max_size: int = 10) -> list[MatchScore]:
    item: models.Item | None = (
        db.query(models.Item)
        .filter(models.Item.id == item_id)
        .first()
    )

    if item is None:
        return []

    matcher = ItemMatcher(max_size)

    candidates = (
        db.query(models.Item).filter(models.Item.id != item_id)
        .yield_per(100)
    )

    for candidate in candidates:
        match_score = calculate_match_score(item, candidate)
        matcher.add(match_score)

    return matcher.get_sorted()
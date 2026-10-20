import heapq
import string
from itertools import count

from database import models
from sqlalchemy.orm import Session

from matching.match_score import MatchScore

# How many suggestions each item keeps
MAX_SUGGESTIONS = 5

# A shortlist of common words that dont say anything about the item.
COMMON_WORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "but", "nor", "so",
        "about", "above", "after", "around", "at", "before", "behind", "below",
        "beside", "between", "by", "during", "for", "from", "in", "inside",
        "into", "near", "next", "of", "off", "on", "onto", "out", "outside",
        "over", "through", "to", "under", "up", "with", "without",
        "i", "me", "my", "mine", "we", "us", "our", "you", "your", "he", "him",
        "his", "she", "her", "it", "its", "they", "them", "their", "this",
        "that", "these", "those", "some", "any", "all", "each", "one",
        "am", "is", "are", "was", "were", "be", "been", "being", "has", "have",
        "had", "do", "does", "did", "could", "will", "would", "should", "may",
        "might", "as", "if", "then", "than", "there", "here", "where", "when",
        "also", "just", "very", "not", "no", "maybe", "probably", "somewhere",
        "lost", "found",
    }
)


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

def words(text: str) -> list[str]:
    """Lowercase the words, strip punctuation, and remove common words"""
    stripped = (w.strip(string.punctuation) for w in text.lower().split())
    return [w for w in stripped if w and w not in COMMON_WORDS]


def calculate_match_score(item: models.Item, candidate: models.Item) -> MatchScore:
    item_words = words(item.description)
    candidate_words = set(words(candidate.description))

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


def get_potential_matches(db: Session, item_id: int, max_size: int = MAX_SUGGESTIONS) -> list[MatchScore]:
    """ Create list of potential matches with the highest scores, the best first.
    Only compares open items of the opposite type (lost/found).
    Pairs with no words in common are left out."""
    item: models.Item | None = (
        db.query(models.Item)
        .filter(models.Item.id == item_id)
        .first()
    )

    if item is None or item.status is not models.ItemStatus.OPEN:
        return []

    other_type = (
        models.ItemType.FOUND if item.type == models.ItemType.LOST else models.ItemType.LOST
    )

    matcher = ItemMatcher(max_size)

    candidates = (
        db.query(models.Item)
        .filter(
            models.Item.id != item_id,
            models.Item.type == other_type,
            models.Item.status == models.ItemStatus.OPEN,
        )
        .yield_per(100)
    )

    for candidate in candidates:
        match_score = calculate_match_score(item, candidate)
        if match_score.score > 0:
            matcher.add(match_score)

    return matcher.get_sorted()
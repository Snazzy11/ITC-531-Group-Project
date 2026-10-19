from dataclasses import dataclass


@dataclass
class MatchScore:
    item_id: int
    prospective_match_item_id: int
    score: float

    def __lt__(self, other):
        return self.score < other.score
    def __gt__(self, other):
        return self.score > other.score
    def __le__(self, other):
        return self.score <= other.score
    def __ge__(self, other):
        return self.score >= other.score
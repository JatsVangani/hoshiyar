"""Short Hindi questions with answers for HEAVY mode, so the model asks what it knows instead of inventing.

Capitals, old films, old cricket records, roads and landmarks: things a driver can answer without thinking
hard. Working-memory puzzles hurt driving, so there is no arithmetic here. The bank is a JSON file beside
this module; edit it freely, the server reads it at import.
"""

import json
import random
from pathlib import Path

BANK: list[dict] = json.loads((Path(__file__).parent / "trivia.json").read_text(encoding="utf-8"))  # Hindi
BANKS: dict[str, list[dict]] = {  # the other languages: trivia.<lang>.json beside this module
    f.stem.split(".")[1]: json.loads(f.read_text(encoding="utf-8"))
    for f in Path(__file__).parent.glob("trivia.*.json")
}
BATCH = 5  # questions handed to the model at a time


def fresh(asked: list[str], n: int = BATCH, lang: str = "hi") -> list[dict]:
    """n questions not yet asked on this call, mixed across topics; starts over when the bank runs dry."""
    bank = BANKS.get(lang, BANK)
    pool = [item for item in bank if item["q"] not in asked] or list(bank)
    random.shuffle(pool)
    picked, seen_topics = [], []
    for item in pool:  # one per topic first, then whatever is left
        if item["t"] not in seen_topics:
            picked.append(item); seen_topics.append(item["t"])
        if len(picked) == n:
            break
    for item in pool:
        if len(picked) == n:
            break
        if item not in picked:
            picked.append(item)
    asked.extend(item["q"] for item in picked)
    return [{"q": item["q"], "a": item["a"]} for item in picked]

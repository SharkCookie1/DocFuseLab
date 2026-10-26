"""Illustrative selector example with fixed unit costs; not an experiment."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "protocols"))

from core57 import pack_order
from method72_frozen import select

row = {
    "units": [
        {"id": 1, "tokens": 10, "text": "Riverbank was written by Lin Zhou."},
        {"id": 2, "tokens": 10, "text": "Lin Zhou was born in Haicheng."},
        {"id": 3, "tokens": 10, "text": "Lin Zhou was born in Shancheng."},
        {"id": 4, "tokens": 10, "text": "Riverbank is a novel."},
    ],
    "rank_order": [1, 2, 4, 3],
}
graph = {
    "families": [
        {"family_id": "A", "chains": [[1, 2]]},
        {"family_id": "B", "chains": [[1, 3]]},
    ],
    "conflicts": [["A", "B"]],
}
budget = 30
joint = select(row, graph, {"selected_ids": [1, 2, 4]}, budget, "joint")
print(json.dumps({
    "note": "Illustrative fixed costs, not measured tokenizer counts.",
    "budget": budget,
    "plain_priority_packing": pack_order(row, row["rank_order"], budget),
    "joint_preservation": joint["ids"],
    "joint_declared_tokens": joint["declared_tokens"],
}, indent=2))


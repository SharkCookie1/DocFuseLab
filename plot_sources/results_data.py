"""Render DocFuseLab paper figures from the supplied, unmodified result summaries.

This program performs no model inference. Used by plot_results.py; original data checks are preserved.
All plotted values are derived from the JSON sources; no synthetic points or fitted
relationships are added. Saved intervals are copied from the original analyses.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import string
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
BLUE = "#4C72A3"
RED = "#B74040"
GREEN = "#688A73"
GRAY = "#7A7F87"
LIGHT = "#DADDE2"
SAND = "#D8C29C"
CORE = ["plain_set", "set_graph", "strong_chain", "joint"]
FIGURES = ["Fig3_main_comparison", "Fig4_budget_sensitivity", "Fig5_conflict_side_intervention", "FigS1_bridge_intervention"]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_rate(k, n, rate, label):
    require(n > 0 and float(n).is_integer(), f"{label}: invalid denominator {n}")
    require(0 <= k <= n and float(k).is_integer(), f"{label}: invalid numerator {k}")
    require(math.isclose(k / n, rate, abs_tol=1e-10), f"{label}: count/rate mismatch")


def validate_comparison(comp, k_joint, k_plain, n, label, delta_key="delta", interval_key="percentile95"):
    require(comp["n"] == n, f"{label}: denominator mismatch")
    require(comp["wins"] + comp["losses"] + comp["ties"] == n, f"{label}: paired counts do not sum to n")
    require(comp["wins"] - comp["losses"] == k_joint - k_plain, f"{label}: paired difference mismatch")
    require(math.isclose(comp[delta_key], (k_joint - k_plain) / n, abs_tol=1e-10), f"{label}: rate difference mismatch")
    lo, hi = comp[interval_key]
    require(-1 <= lo <= comp[delta_key] <= hi <= 1, f"{label}: invalid saved interval")


def normalized_answer(text):
    text = str(text).lower()
    text = "".join(ch for ch in text if ch not in string.punctuation)
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(text.split())


def classify_side_responses(data):
    """Classify all 9 observed answers; 'remaining' is a side label, not accuracy."""
    counts = {v: {c: 0 for c in ["conflict", "remaining", "other", "unknown"]}
              for v in ["intact", "sham", "critical"]}
    audit = []
    questions = sorted([q for q in data["details"] if q["group"] == "side"], key=lambda q: q["qid"])
    require(len(questions) == 9, "Conflict-side intervention must contain 9 questions")
    for question_index, q in enumerate(questions, 1):
        aliases = {normalized_answer(a) for a in q["arms"]["critical"]["context_expected_aliases"]}
        require(aliases and "conflict" not in aliases and "unknown" not in aliases, "Invalid remaining-side aliases")
        for v in counts:
            a = q["arms"][v]
            require(a["valid"], f"Invalid response in intervention: {q['qid']}/{v}")
            if a["predicted_conflict"]:
                category = "conflict"
            elif a["predicted_unknown"]:
                category = "unknown"
            elif normalized_answer(a["answer"]) in aliases:
                category = "remaining"
            else:
                category = "other"
            counts[v][category] += 1
            if v == "critical":
                require((category == "remaining") == bool(a["context_appropriate_em"]), "Remaining-answer classification disagrees with saved score")
            audit.append({"question_index": question_index, "qid": q["qid"], "version": v, "answer": a["answer"], "category": category,
                          "remaining_side_aliases": " | ".join(q["arms"]["critical"]["context_expected_aliases"])})
    for v, c in counts.items():
        require(sum(c.values()) == 9, f"Incomplete intervention classification: {v}")
        require(c["conflict"] == data["tables"]["side"][v]["conflict_count"], "Conflict counts differ from summary")
        require(c["unknown"] == data["tables"]["side"][v]["unknown_count"], "Unknown counts differ from summary")
    return counts, audit


def load_and_validate():
    manifest = read_json(DATA / "SOURCE_MANIFEST.json")
    summaries = {}
    for name, meta in manifest["files"].items():
        path = DATA / name
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        require(actual == meta["sha256"], f"Source file changed: {name}. Restore the supplied file before drawing publication figures.")
        summaries[name] = read_json(path)
    A, B, C, D, E = (summaries[n] for n in ["baseline101.json", "baseline102.json", "baseline103.json", "summary104.json", "summary105.json"])
    require(all(x["complete"] for x in [A, B, C, D, E]), "One or more experiments are incomplete")
    dev4 = A["baseline4b_groups"]["all350"]
    dev8 = C["groups"]["all350"]
    main = []
    for key, group, table_key, comp_key in [("development_4b", dev4, "tables", "paired_comparisons"),
                                             ("development_8b", dev8, "tables8b", "selector_comparisons8b")]:
        t = group[table_key]["hotpot_conflict"]
        for arm in t:
            validate_rate(t[arm]["correct"], t[arm]["n"], t[arm]["em"], f"{key}/{arm}")
        comp = group[comp_key]["hotpot_conflict"]["joint_vs_plain_set"]
        k0, k1, n = int(t["plain_set"]["correct"]), int(t["joint"]["correct"]), t["joint"]["n"]
        require(n == 150, "Development conflict denominator must be 150")
        validate_comparison(comp, k1, k0, n, key)
        main.append({"key": key, "n": n, "plain": k0, "joint": k1,
                     "delta": comp["delta"], "interval": comp["percentile95"], "scope": "development_descriptive"})
    n = E["groups"]["conflict"]["planned"]
    require(n == 200 and E["groups"]["clean"]["planned"] == 100, "Confirmation cohort composition changed")
    for group, total in [("conflict", 200), ("clean", 100)]:
        rows = [q for q in E["details"] if q["condition"] == group]
        require(len(rows) == total, f"Confirmation details: {group} count mismatch")
        for arm, t in E["groups"][group]["arms"].items():
            validate_rate(t["correct"], total, t["accuracy"], f"confirmation/{group}/{arm}")
            require(sum(q["arms"][arm]["em"] for q in rows) == t["correct"], "Confirmation row/summary mismatch")
            require(sum(q["arms"][arm]["false_conflict"] for q in rows) == t["false_conflicts"], "False-conflict row/summary mismatch")
    t = E["groups"]["conflict"]["arms"]
    k0, k1 = int(t["plain_set"]["correct"]), int(t["joint"]["correct"])
    validate_comparison(E["primary"], k1, k0, n, "confirmation", "difference", "source_cluster_bootstrap95")
    main.append({"key": "confirmation_8b", "n": n, "plain": k0, "joint": k1,
                 "delta": E["primary"]["difference"], "interval": E["primary"]["source_cluster_bootstrap95"],
                 "scope": "prespecified_confirmation"})
    require(set(B["groups"]) == {"128", "256", "512"}, "Budget levels must be 128, 256 and 512")
    budget_rows = []
    for budget in [128, 256, 512]:
        group = B["groups"][str(budget)]
        for arm, t in group["tables"]["hotpot_conflict"].items():
            require(t["n"] == 146, "Budget sweep uses the same 146 conflict questions")
            validate_rate(t["correct"], t["n"], t["em"], f"budget/{budget}/{arm}")
            budget_rows.append({"budget": budget, "arm": arm, "n": t["n"], "correct": int(t["correct"]), "rate": t["em"]})
        t = group["tables"]["hotpot_conflict"]
        validate_comparison(group["paired_comparisons"]["hotpot_conflict"]["joint_vs_plain_set"], t["joint"]["correct"], t["plain_set"]["correct"], 146, f"budget/{budget}")
    side, side_audit = classify_side_responses(D)
    for v in ["intact", "sham", "critical"]:
        t = D["tables"]["bridge"][v]
        require(t["n"] == 16 and 0 <= t["original_response_count"] + t["unknown_count"] <= 16, "Bridge categories do not partition the 16 responses")
        detail = [q["arms"][v] for q in D["details"] if q["group"] == "bridge"]
        require(len(detail) == 16 and sum(x["original_response_em"] for x in detail) == t["original_response_count"], "Bridge original-response mismatch")
        require(sum(x["predicted_unknown"] for x in detail) == t["unknown_count"], "Bridge UNKNOWN mismatch")
        require(not any(x["predicted_unknown"] and x["original_response_em"] for x in detail), "Bridge response categories overlap")
    return summaries, main, budget_rows, side, side_audit, manifest


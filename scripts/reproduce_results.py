"""Recompute confirmation comparisons from the released numerical records."""
from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARMS = ("plain_set", "setr_iri_budget", "mmr", "set_graph", "strong_chain", "joint")
EXTRA_ARMS = ("full_context", "annotation_reference")


def read_json(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def paired_counts(rows, comparator):
    wins = losses = ties = 0
    for row in rows:
        joint = row["arms"]["joint"]["em"]
        other = row["arms"][comparator]["em"]
        require(joint in (0, 1) and other in (0, 1), "Correctness must be binary.")
        wins += joint > other
        losses += joint < other
        ties += joint == other
    discordant = wins + losses
    probability = (
        min(1.0, 2 * sum(math.comb(discordant, k) for k in range(min(wins, losses) + 1))
            / (2 ** discordant))
        if discordant else 1.0
    )
    return {
        "comparator": comparator,
        "n": len(rows),
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "difference": (wins - losses) / len(rows),
        "exact_mcnemar_p": probability,
    }


def recompute():
    rows = read_json("records/confirmation_outcomes.json")
    summaries = read_json("data/summary106.json")
    require(len(rows) == 300, "Expected 300 confirmation records.")
    require(len({row["qid"] for row in rows}) == 300, "Duplicate question identifier.")
    require(len({row["analysis_cluster"] for row in rows}) == 300, "Repeated confirmation cluster.")
    grouped = {name: [row for row in rows if row["condition"] == name]
               for name in ("conflict", "clean")}
    require(len(grouped["conflict"]) == 200 and len(grouped["clean"]) == 100,
            "Confirmation cohort composition differs from the frozen protocol.")
    totals = []
    for name, group in grouped.items():
        for arm in ARMS + EXTRA_ARMS:
            outcomes = [row["arms"][arm] for row in group]
            if arm in ARMS:
                require(all(outcome["source_tokens"] <= 256 for outcome in outcomes),
                        f"Source-token cap exceeded: {name}/{arm}.")
            total = {
                "condition": name,
                "arm": arm,
                "n": len(group),
                "correct": int(sum(outcome["em"] for outcome in outcomes)),
                "accuracy": sum(outcome["em"] for outcome in outcomes) / len(group),
                "mean_f1": sum(outcome["f1"] for outcome in outcomes) / len(group),
                "false_conflicts": int(sum(outcome["false_conflict"] for outcome in outcomes)),
                "mean_source_tokens": sum(outcome["source_tokens"] for outcome in outcomes) / len(group),
            }
            saved = summaries["groups"][name]["arms"][arm]
            for key in ("correct", "accuracy", "mean_f1", "false_conflicts", "mean_source_tokens"):
                require(math.isclose(total[key], saved[key], rel_tol=1e-10, abs_tol=1e-10),
                        f"Numerical record and summary disagree: {name}/{arm}/{key}.")
            totals.append(total)

    comparisons = [paired_counts(grouped["conflict"], arm)
                   for arm in ("plain_set", "setr_iri_budget", "strong_chain")]
    reference = read_json("records/reference_diagnostics.json")
    resolved = reference["resolved"]
    feasible = [row for row in resolved
                if row["condition"] == "conflict" and row["reviewed_reference"]["fits256"]]
    diagnostic = {
        "resolved_cases": len(resolved),
        "feasible_conflict_references": len(feasible),
        "reference_correct": int(sum(row["reviewed_reference"]["correct"] for row in feasible)),
        "joint_correct": int(sum(row["prior_correct"]["joint"] for row in feasible)),
    }
    require(diagnostic == {"resolved_cases": 55, "feasible_conflict_references": 29,
                           "reference_correct": 18, "joint_correct": 6},
            "Reference diagnostic differs from the reported values.")
    return {"confirmation": totals, "paired_conflict_comparisons": comparisons,
            "reference_diagnostic": diagnostic}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figures", action="store_true",
                        help="Also regenerate the two empirical figures (requires matplotlib and numpy).")
    args = parser.parse_args()
    print("Checking numerical records...", flush=True)
    report = recompute()
    output = ROOT / "reproduced"
    output.mkdir(exist_ok=True)
    (output / "confirmation_checks.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with (output / "confirmation_results.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=report["confirmation"][0].keys())
        writer.writeheader()
        writer.writerows(report["confirmation"])
    print("Rebuilding the eight manuscript tables...", flush=True)
    (ROOT / "tables").mkdir(exist_ok=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/build_tables.py")],
                   check=True, cwd=ROOT)
    if args.figures:
        print("Rebuilding empirical figures...", flush=True)
        subprocess.run([sys.executable, str(ROOT / "plot_sources/generate_paper_figures.py")],
                       check=True, cwd=ROOT)
    print("Complete. Recomputed records: reproduced/; manuscript tables: tables/.", flush=True)


if __name__ == "__main__":
    main()


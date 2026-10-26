"""Regenerate only the two empirical figures used by the manuscript."""
from pathlib import Path

try:
    from plot_results import configure_style, budget_sensitivity, intervention_matrix
    from results_data import load_and_validate
except ModuleNotFoundError as exc:
    raise SystemExit('Plotting dependency missing. Use an environment with matplotlib and numpy installed. No model inference is required.\n' + str(exc)) from exc

print('Checking recorded figure data...', flush=True)
summaries, _, _, side, side_audit, _ = load_and_validate()
configure_style('stix')
out = Path(__file__).resolve().parents[1] / 'figures'
out.mkdir(exist_ok=True)
print('Rendering budget figure...', flush=True)
budget_sensitivity(summaries['baseline102.json'], out, 600)
print('Rendering source-intervention figure...', flush=True)
intervention_matrix(side_audit, side, 9, out, 'Fig5_conflict_side_intervention', 600)
print('Complete. English PDF, SVG, and PNG figures: ' + str(out), flush=True)

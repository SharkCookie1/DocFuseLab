# DocFuseLab

Analysis data and method code for **Preserving complete evidence chains and opposing support under context budgets**.

The selector preserves complete source-grounded evidence families and opposing support within a fixed reader source-token budget. This repository contains the numerical results and frozen selection components used in the manuscript.

## Reproduce the reported results

Python 3.10 or later is sufficient to recompute the confirmation comparisons and rebuild all eight tables. No model weights, GPU, or network connection are needed for this command.

~~~bash
python scripts/reproduce_results.py
~~~

The script checks all 300 confirmation records against the saved summaries, recomputes paired counts and exact McNemar probabilities, checks the reference-input diagnostic, and writes CSV and JSON results to reproduced/. The eight LaTeX tables are written to tables/.

To also regenerate the two empirical figures, install the plotting dependencies once and run:

~~~bash
python -m pip install -r requirements-figures.txt
python scripts/reproduce_results.py --figures
~~~

The empirical figures are saved as PDF, SVG, and PNG in figures/. The installation command is separate from the analysis command; running the analysis never starts a dependency download. On Windows, RUN_TABLES.cmd performs the standard-library analysis and RUN_FIGURES.cmd also draws the figures using an already prepared Python environment.

The plotting scripts retain historical names: Fig4_budget_sensitivity is Figure 7 in the manuscript, and Fig5_conflict_side_intervention is Figure 8.

## Inspect the selection mechanism

~~~bash
python scripts/demo_selector.py
~~~

This small illustrative example invokes the frozen family-closure selector in protocols/method72_frozen.py. It uses stipulated unit costs to show how plain priority packing and joint preservation can retain different evidence. It is not an additional experiment and does not estimate tokenizer costs.

The central implementation is protocols/method60.py, with conservative family closure in protocols/method72_frozen.py and the frozen interfaces in the surrounding modules. The protocols directory preserves historical module names so imports and recorded configurations remain traceable. These method snapshots document the model-facing protocol; they are not a standalone installer for rerunning every GPU experiment.

## Repository contents

| Path | Contents |
| --- | --- |
| records/ | Per-question numerical outcomes for 300 confirmation questions and the resolved reference diagnostic |
| data/ | Aggregate inputs for the manuscript tables |
| protocols/ | Frozen methods, prompts, configurations, recorded software versions, and hardware description |
| scripts/ | Numerical checks, table generation, and an illustrative selector example |
| plot_sources/ | Plotting code, checked result inputs, and font licenses |
| figure_sources/ | Editable source objects and PowerPoint for the six schematics |
| figures/ | The eight publication figure PDFs |
| tables/ | The eight manuscript tables |
| SOURCE_PROVENANCE.json | Provenance and hashes for the retained analysis inputs |

## Data scope

The primary confirmation contains 200 controlled conflict variants and 100 ordinary questions from 2WikiMultihopQA. Development analyses use the HotpotQA portion of FaithEval-inconsistent and ordinary HotpotQA questions. The original conditions and all completed outcomes remain in the numerical comparisons.

The compact confirmation records contain question and source identifiers, selected-unit identifiers, correctness indicators, source-token counts, and cost accounting. The reference records distinguish the 55 resolved diagnostic cases from the five unresolved cases retained in the primary analysis. The development, budget, and intervention analysis inputs retain the fields needed by the released tables and figures. This is an analysis release, not the full archive of model calls or original candidate passages.

Original dataset text and model weights are not distributed here. Public source definitions and pinned revisions are recorded in the protocols and cited in the paper.

## Experimental environment

The model experiments used a Windows 11 laptop with an Intel Core Ultra 9 275HX, 32 GB system memory, and one NVIDIA GeForce RTX 5060 Laptop GPU with nominal 8 GB GPU memory. Hardware details are in protocols/hardware.json; the recorded model environment is in protocols/recorded_environment.json. The lightweight analysis requirements are separate from that inference environment.

## Rights and citation

Third-party fonts retain the notices supplied in their directories. Public datasets and model assets remain governed by their upstream terms. See LICENSE_NOTICE.txt for the current project licensing status. CITATION.cff identifies this analysis release and the associated manuscript.

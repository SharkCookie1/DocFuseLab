"""Publication figures from the supplied DocFuseLab results.

Run ``python plot_results.py``. All output is English and goes directly to output/.
The source summaries, their denominators, and their saved uncertainty intervals
are unchanged. No model inference, synthetic observations, or regression is run.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
import numpy as np

from results_data import load_and_validate, require

ROOT = Path(__file__).resolve().parent
WIDTH = 7.1  # Journal two-column width in inches; export does not crop the canvas.
BLUE = "#527493"
RED = "#A95858"
SAGE = "#7E8F79"
GRAY = "#899199"
INK = "#242424"
GRID = "#E3E5E7"
CORE = ["plain_set", "set_graph", "strong_chain", "joint"]
FILES = ["Fig3_main_comparison", "Fig4_budget_sensitivity", "Fig5_conflict_side_intervention", "FigS1_bridge_intervention"]


def configure_style(font_choice):
    bundled = ROOT / "fonts"
    for p in sorted(bundled.glob("STIXGeneral*.ttf")):
        font_manager.fontManager.addfont(str(p))
    available = {f.name for f in font_manager.fontManager.ttflist}
    if font_choice == "times":
        require("Times New Roman" in available, "Times New Roman was requested but is not installed. Use --font auto or --font stix.")
        family = "Times New Roman"
    elif font_choice == "auto" and "Times New Roman" in available:
        family = "Times New Roman"
    else:
        require("STIXGeneral" in available, "Bundled STIX serif font is missing. Extract the complete package, including fonts/.")
        family = "STIXGeneral"
    matplotlib.rcParams.update({
        "font.family": family, "font.size": 8.3,
        "axes.labelsize": 8.6, "axes.titlesize": 8.8,
        "xtick.labelsize": 7.8, "ytick.labelsize": 8.0,
        "legend.fontsize": 8.0, "axes.linewidth": .65,
        "axes.edgecolor": INK, "text.color": INK,
        "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
        "xtick.major.width": .55, "ytick.major.width": .55,
        "xtick.major.size": 3, "ytick.major.size": 3,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.axisbelow": True, "axes.unicode_minus": False,
        "grid.color": GRID, "grid.linewidth": .45,
        "figure.facecolor": "white", "axes.facecolor": "white",
        "savefig.facecolor": "white", "pdf.fonttype": 42,
        "ps.fonttype": 42, "svg.fonttype": "path", "mathtext.fontset": "stix",
    })
    return family


def panel(ax, text):
    ax.text(0, 1.045, text, transform=ax.transAxes, va="bottom", ha="left", fontsize=9, fontweight="bold")


def save(fig, outdir, name, dpi):
    require(abs(fig.get_figwidth() - WIDTH) < 1e-8, "Unexpected figure width")
    for ext in ["png", "pdf", "svg"]:
        target=outdir / f"{name}.{ext}"
        temporary=outdir / f"{name}.{ext}.tmp"
        fig.savefig(temporary, format=ext, dpi=dpi)
        require(temporary.stat().st_size > 512, f"Empty or incomplete figure export: {name}.{ext}")
        temporary.replace(target)
    plt.close(fig)


def main_comparison(rows, outdir, dpi):
    fig, axs = plt.subplots(1, 2, figsize=(WIDTH, 2.72), sharey=True,
                            gridspec_kw={"width_ratios": [1.12, 1]})
    fig.subplots_adjust(left=.185, right=.985, top=.88, bottom=.25, wspace=.28)
    names = ["Development, 4B\n(n = 150)", "Development, 8B\n(n = 150)", "Confirmation, 8B\n(n = 200)"]
    ypos = [2, 1, 0]
    for y, r in zip(ypos, rows):
        plain, joint = 100*r["plain"]/r["n"], 100*r["joint"]/r["n"]
        axs[0].plot([plain, joint], [y, y], lw=.8, color="#B5BCC2", zorder=2)
        axs[0].plot(plain, y, "o", mfc="white", mec=BLUE, mew=1.0, ms=4.4, zorder=4)
        axs[0].plot(joint, y, "s", mfc=RED, mec=RED, mew=.7, ms=4.2, zorder=4)
        axs[0].text(plain, y-.23, f"{plain:.1f}", color=BLUE, ha="center", va="top", fontsize=7.4)
        axs[0].text(joint, y+.20, f"{joint:.1f}", color=RED, ha="center", va="bottom", fontsize=7.4)
        d, lo, hi = 100*r["delta"], 100*r["interval"][0], 100*r["interval"][1]
        axs[1].errorbar(d, y, xerr=[[d-lo], [hi-d]], fmt="s" if y==0 else "o",
                        color=RED, mfc=RED if y==0 else "white", mec=RED, mew=.85,
                        ms=4.6, capsize=2.6, elinewidth=1.0, zorder=4)
        axs[1].text(d, y+.19, f"+{d:.1f}", color=RED, ha="center", va="bottom", fontsize=7.5)
    axs[0].set(yticks=ypos, yticklabels=names, ylim=(-.48, 2.50),
               xlim=(0, 50), xticks=[0, 10, 20, 30, 40, 50], xlabel="Conflict identification (%)")
    axs[0].tick_params(axis="y", length=0, pad=7)
    axs[1].set(xlim=(-2, 22), xticks=[0, 5, 10, 15, 20], xlabel="Paired gain (percentage points)")
    axs[1].tick_params(axis="y", left=False, labelleft=False)
    axs[1].axvline(0, color="#7D8388", lw=.65, ls=(0, (3, 3)))
    for ax in axs:
        ax.grid(axis="y")
    panel(axs[0], "(a)")
    panel(axs[1], "(b)")
    handles=[Line2D([], [], marker="o", mfc="white", mec=BLUE, color="none", ms=4.5, label="Plain set"),
             Line2D([], [], marker="s", mfc=RED, mec=RED, color="none", ms=4.3, label="Joint preservation")]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.57, .01), ncol=2, frameon=False,
               handletextpad=.4, columnspacing=1.8)
    save(fig, outdir, FILES[0], dpi)


def budget_sensitivity(B, outdir, dpi):
    fig, axs = plt.subplots(1, 2, figsize=(WIDTH, 2.82), gridspec_kw={"width_ratios": [1.08, 1]})
    fig.subplots_adjust(left=.080, right=.985, top=.88, bottom=.28, wspace=.36)
    budgets=[128, 256, 512]
    names={"plain_set":"Plain set", "set_graph":"Same-graph set", "strong_chain":"Chain closure", "joint":"Joint preservation"}
    colors={"plain_set":BLUE, "set_graph":GRAY, "strong_chain":SAGE, "joint":RED}
    for arm, marker, ls in zip(CORE, ["D", "s", "^", "o"], [(0,(4,2)), (0,(1,2)), (0,(5,2)), "-"]):
        values=[100*B["groups"][str(b)]["tables"]["hotpot_conflict"][arm]["em"] for b in budgets]
        axs[0].plot(budgets, values, color=colors[arm], marker=marker, lw=1.1, ls=ls,
                    ms=6.1 if arm=="strong_chain" else 3.7,
                    mfc="white" if arm!="joint" else RED, mec=colors[arm], mew=.8,
                    label=names[arm], zorder=5 if arm=="joint" else 3)
    axs[0].set(xlim=(110, 530), xticks=budgets, ylim=(0, 50), yticks=[0,10,20,30,40,50],
               xlabel="Evidence budget (tokens)", ylabel="Conflict identification (%)")
    for b in budgets:
        c=B["groups"][str(b)]["paired_comparisons"]["hotpot_conflict"]["joint_vs_plain_set"]
        d,lo,hi=100*c["delta"],100*c["percentile95"][0],100*c["percentile95"][1]
        axs[1].errorbar(b, d, yerr=[[d-lo],[hi-d]], fmt="o", color=RED, ms=4.2,
                        capsize=2.7, elinewidth=1.0, mew=.8, zorder=3)
        axs[1].text(b, hi+.7, f"+{d:.1f}", ha="center", va="bottom", color=RED, fontsize=7.6)
    axs[1].axhline(0, color="#7D8388", lw=.65, ls=(0,(3,3)))
    axs[1].set(xticks=budgets, xlim=(110,530), ylim=(-5,22), yticks=[-5,0,5,10,15,20],
               xlabel="Evidence budget (tokens)", ylabel="Paired gain (percentage points)")
    for ax in axs:
        ax.grid(axis="y")
    panel(axs[0], "(a)")
    panel(axs[1], "(b)")
    h,l=axs[0].get_legend_handles_labels()
    fig.legend(h,l,loc="lower center",bbox_to_anchor=(.54,.012),ncol=4,frameon=False,
               handlelength=2.2,handletextpad=.5,columnspacing=1.5)
    save(fig,outdir,FILES[1],dpi)


def classify_bridge(data):
    rows=[]
    for idx,q in enumerate(sorted([q for q in data["details"] if q["group"]=="bridge"],key=lambda q:q["qid"]),1):
        for version in ["intact","sham","critical"]:
            a=q["arms"][version]
            if a["predicted_unknown"]:
                cat="unknown"
            elif a["original_response_em"]:
                cat="original"
            else:
                cat="other"
            rows.append({"question_index":idx,"qid":q["qid"],"version":version,"answer":a["answer"],"category":cat})
    return rows


def intervention_matrix(audit, counts, n, outdir, filename, dpi, bridge=False):
    """One observed output per symbol; columns follow sorted question IDs, not scores."""
    versions=["intact","sham","critical"]
    if bridge:
        categories=["original","other","unknown"]
        names={"original":"A: Original answer","other":"O: Other answer","unknown":"U: UNKNOWN"}
        short={"original":"A","other":"O","unknown":"U"}
    else:
        categories=["conflict","remaining","other","unknown"]
        names={"conflict":"C: CONFLICT","remaining":"R: Retained-side answer","other":"O: Other answer","unknown":"U: UNKNOWN"}
        short={"conflict":"C","remaining":"R","other":"O","unknown":"U"}
    marker={"conflict":"o","remaining":"s","original":"s","other":"D","unknown":"x"}
    color={"conflict":RED,"remaining":BLUE,"original":BLUE,"other":GRAY,"unknown":"#50565B"}
    fig,ax=plt.subplots(figsize=(WIDTH,2.34))
    fig.subplots_adjust(left=.19,right=.985,bottom=.32,top=.82)
    count_start=n+1.15
    ax.set_xlim(.35,count_start+len(categories)-.35)
    ax.set_ylim(-.48,2.48)
    for y in [0,1,2]:
        ax.hlines(y,.65,n+.35,color=GRID,lw=.5,zorder=1)
    ax.axvline(n+.70,color="#BFC4C8",lw=.6)
    for vi,version in enumerate(versions):
        y=2-vi
        for category in categories:
            selected=[r["question_index"] for r in audit if r["version"]==version and r["category"]==category]
            require(len(selected)==counts[version][category],"Matrix symbols disagree with verified counts")
            if selected:
                kwargs={"marker":marker[category],"linestyle":"none","ms":5.1 if n==9 else 4.5,
                        "color":color[category],"mew":.85,"zorder":3}
                if category=="other":kwargs["mfc"]="white"
                ax.plot(selected,[y]*len(selected),**kwargs)
            cx=count_start+categories.index(category)
            ax.text(cx,y,str(counts[version][category]),ha="center",va="center",fontsize=8.2,color=INK)
    for j,category in enumerate(categories):
        ax.text(count_start+j,2.48,short[category],ha="center",va="bottom",fontsize=8.0,color=color[category])
    ax.text((n+1)/2,2.82,"Matched questions",ha="center",va="bottom",fontsize=8.7)
    ax.text(count_start+(len(categories)-1)/2,2.82,"Counts",ha="center",va="bottom",fontsize=8.7)
    ax.set(xticks=list(range(1,n+1)),xticklabels=[str(i) for i in range(1,n+1)],
           yticks=[2,1,0],yticklabels=["Intact evidence","Sham replacement","Critical replacement"])
    ax.tick_params(axis="x",length=0,pad=7,labelsize=7.5)
    ax.tick_params(axis="y",length=0,pad=8,labelsize=8.2)
    for spine in ax.spines.values():spine.set_visible(False)
    handles=[]
    for category in categories:
        handles.append(Line2D([],[],marker=marker[category],color=color[category],linestyle="none",
                              mfc="white" if category=="other" else color[category],mew=.85,ms=4.7,label=names[category]))
    fig.legend(handles=handles,loc="lower center",bbox_to_anchor=(.54,.02),ncol=len(categories),frameon=False,
               fontsize=7.6,handlelength=1.0,handletextpad=.35,columnspacing=1.35)
    save(fig,outdir,filename,dpi)


def write_csv(path,rows):
    with path.open("w",encoding="utf-8-sig",newline="") as stream:
        fields=list(dict.fromkeys(k for row in rows for k in row))
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def main():
    start=time.perf_counter()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,default=ROOT/"output")
    parser.add_argument("--dpi",type=int,default=600)
    parser.add_argument("--font",choices=["auto","times","stix"],default="auto")
    args=parser.parse_args()
    require(150<=args.dpi<=1200,"DPI must be between 150 and 1200")
    summaries,main_rows,budget_rows,side,side_audit,manifest=load_and_validate()
    family=configure_style(args.font)
    B,D,E=(summaries[n] for n in ["baseline102.json","summary104.json","summary105.json"])
    args.output.mkdir(parents=True,exist_ok=True)
    bridge={v:{"original":int(D["tables"]["bridge"][v]["original_response_count"]),
               "unknown":D["tables"]["bridge"][v]["unknown_count"],
               "other":16-int(D["tables"]["bridge"][v]["original_response_count"])-D["tables"]["bridge"][v]["unknown_count"]}
            for v in ["intact","sham","critical"]}
    bridge_audit=classify_bridge(D)
    main_comparison(main_rows,args.output,args.dpi)
    budget_sensitivity(B,args.output,args.dpi)
    intervention_matrix(side_audit,side,9,args.output,FILES[2],args.dpi)
    intervention_matrix(bridge_audit,bridge,16,args.output,FILES[3],args.dpi,bridge=True)
    rows=[{"cohort":r["key"],"conflict_n":r["n"],"plain_correct":r["plain"],"joint_correct":r["joint"],
           "plain_rate_pct":100*r["plain"]/r["n"],"joint_rate_pct":100*r["joint"]/r["n"],"gain_pp":100*r["delta"],
           "interval_low_pp":100*r["interval"][0],"interval_high_pp":100*r["interval"][1],"interval_scope":r["scope"]} for r in main_rows]
    write_csv(args.output/"main_figure_data.csv",rows)
    write_csv(args.output/"budget_figure_data.csv",budget_rows)
    write_csv(args.output/"side_response_classification.csv",side_audit)
    write_csv(args.output/"bridge_response_classification.csv",bridge_audit)
    write_csv(args.output/"mechanism_figure_data.csv",[{"group":g,"version":v,"n":n,**c} for g,n,ds in [("side",9,side),("bridge",16,bridge)] for v,c in ds.items()])
    elapsed=time.perf_counter()-start
    receipt={"status":"passed","no_model_inference":True,"language":"English","figure_width_inches":WIDTH,
             "matplotlib_version":matplotlib.__version__,"python_version":sys.version,"font":family,"dpi":args.dpi,"seconds":elapsed,
             "source_hashes":manifest["files"],"main":rows,"side_response_counts":side,"bridge_response_counts":bridge,
             "ordinary_confirmation":{"n":100,"plain_exact":E["groups"]["clean"]["arms"]["plain_set"]["correct"],
                                      "joint_exact":E["groups"]["clean"]["arms"]["joint"]["correct"],
                                      "plain_false_conflicts":E["groups"]["clean"]["arms"]["plain_set"]["false_conflicts"],
                                      "joint_false_conflicts":E["groups"]["clean"]["arms"]["joint"]["false_conflicts"]}}
    (args.output/"validation_receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Created 4 English figures in PNG/PDF/SVG: {args.output}",flush=True)
    print(f"Data checks passed. Font: {family}. Width: {WIDTH} inches. Rendering: {elapsed:.1f} seconds.",flush=True)
    print("No model inference, synthetic data, or new statistical fitting was performed.",flush=True)


if __name__=="__main__":
    main()

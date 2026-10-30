"""
Replicate Coimbra & Rey (2024, REStud) stylized facts, Figures 1-2, on the BankFocus panel.

Usage: python stylized_facts.py <bankfocus_panel_main.csv> <out_dir>

Fig 1: quantiles of each year's cross-section of asset-weighted leverage
       AWlev_it = lev_it * TA_it / mean_t(TA), rebased to 100 in the base year.
Fig 2: mean leverage by asset decile / equity decile, pre-crisis pooled sample.
Samples: (a) 400 largest US banks 1997-2025, unweighted, base 1997 ; (b) North America + Europe 2005-2025, base 2005
         (Europe has no BankFocus data before 2005).
"""
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker

SRC = sys.argv[1] if len(sys.argv) > 1 else "bankfocus_panel_main.csv"
OUT = sys.argv[2] if len(sys.argv) > 2 else "."

C = {"blue": "#2a78d6", "orange": "#eb6834", "aqua": "#1baf7a", "yellow": "#eda100"}
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e4e3dd"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.6, "lines.linewidth": 2, "figure.dpi": 150})

d = pd.read_csv(SRC, low_memory=False)
d = d[(d["network_member"] == 0) & d["leverage"].notna() & (d["ta"] > 0)].copy()
# winsorize leverage at 1/99% within each year (special-purpose vehicles have leverage in the 100s-1000s)
g = d.groupby("year")["leverage"]
d["leverage"] = d["leverage"].clip(g.transform(lambda x: x.quantile(0.01)), g.transform(lambda x: x.quantile(0.99)))


def aw_quantiles(s, qs, weighted=True):
    s = s.copy()
    s["awlev"] = s["leverage"] * (s["ta"] / s.groupby("year")["ta"].transform("mean") if weighted else 1)
    return s.groupby("year")["awlev"].quantile(qs).unstack()


def fig1(s, base, title, fname, weighted=True):
    q = aw_quantiles(s, [0.05, 0.50, 0.90, 0.95], weighted)
    idx = q.div(q.loc[base]) * 100
    dense = aw_quantiles(s, [0.75, 0.80, 0.85, 0.90, 0.95, 0.99], weighted)
    dense = dense.div(dense.loc[base]) * 100

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
    spec = [(0.95, "Top 5%", C["blue"]), (0.90, "Top 10%", C["orange"]),
            (0.50, "Median", C["aqua"]), (0.05, "Bottom 5%", C["yellow"])]
    for qv, lab, col in spec:
        ax[0].plot(idx.index, idx[qv], color=col, label=lab)
    ax[0].set_title("Selected quantiles", loc="left", color=INK)
    ramp = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#104281"]
    for col, qv in zip(ramp, dense.columns):
        ax[1].plot(dense.index, dense[qv], color=col, label=f"p{int(qv*100)}")
    ax[1].set_title("Quantiles above the 75th", loc="left", color=INK)
    for a in ax:
        a.axhline(100, color=MUTED, lw=0.8, ls=":")
        a.axvspan(2007.5, 2009.5, color=GRID, alpha=0.6, lw=0)
        a.set_ylabel(f"Index ({base} = 100)")
        a.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(1.0, 1.0))
        a.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    fig.suptitle(title, x=0.01, ha="left", color=INK, fontsize=12)
    fig.tight_layout()
    fig.savefig(f"{OUT}/{fname}", bbox_inches="tight")
    plt.close(fig)
    return idx


def fig2(s, title, fname):
    s = s.copy()
    lo, hi = s["leverage"].quantile([0.01, 0.99])
    s["lev_w"] = s["leverage"].clip(lo, hi)
    s["a_dec"] = pd.qcut(s["ta"], 10, labels=range(1, 11))
    s["e_dec"] = pd.qcut(s["te"], 10, labels=range(1, 11))
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    for a, key, lab in [(ax[0], "a_dec", "Asset decile"), (ax[1], "e_dec", "Equity decile")]:
        m = s.groupby(key, observed=True)["lev_w"].mean()
        a.plot(m.index.astype(int), m.values, "o-", color=C["blue"], ms=6, mfc="white", mew=2)
        a.set_xlabel(lab); a.set_xticks(range(1, 11))
    ax[0].set_ylabel("Mean leverage (assets / equity)")
    fig.suptitle(title, x=0.01, ha="left", color=INK, fontsize=12)
    fig.tight_layout()
    fig.savefig(f"{OUT}/{fname}", bbox_inches="tight")
    plt.close(fig)
    n = s.groupby("a_dec", observed=True)["bvdid"].nunique()
    return s.groupby("a_dec", observed=True)["lev_w"].mean(), n


us = d[d["iso2"] == "US"]
both = d[d["year"] >= 2005]
# US: coverage doubles in 2001 and asset concentration rises, which mechanically pulls the
# asset-weighted measure down. Use a constant-size cross-section (400 largest US banks each year,
# close to the paper's ~410 intermediaries) and unweighted leverage quantiles.
us400 = us[us.groupby("year")["ta"].rank(ascending=False) <= 400]
i_us = fig1(us400, 1997, "Leverage by quantile — 400 largest US banks, unweighted (1997 = 100)",
            "fig1_us400_1997.png", weighted=False)
i_all = fig1(both, 2005, "Asset-weighted leverage by quantile — North America + Europe (2005 = 100)",
             "fig1_na_eu_2005.png")
m_us, n_us = fig2(us[us["year"] <= 2007], "Mean leverage by size and equity decile — US, 1997–2007",
                  "fig2_us_precrisis.png")
m_all, n_all = fig2(both[both["year"] <= 2007], "Mean leverage by size and equity decile — NA + Europe, 2005–2007",
                    "fig2_na_eu_precrisis.png")

# summary numbers
with open(f"{OUT}/stylized_facts_summary.txt", "w") as f:
    for lab, i in [("US 400 largest, unweighted, 1997=100", i_us), ("NA+EU, 2005=100", i_all)]:
        f.write(f"\n{lab}\n" + i.loc[[y for y in [1997, 2000, 2005, 2007, 2008, 2010, 2015, 2020, 2025]
                                     if y in i.index]].round(1).to_string() + "\n")
    q = aw_quantiles(both, [0.95])[0.95]
    f.write(f"\nNA+EU top-5% AW leverage, 2008/2005 ratio: {q[2008] / q[2005]:.2f}\n")
    for lab, m in [("US 1997-2007", m_us), ("NA+EU 2005-2007", m_all)]:
        f.write(f"\nMean leverage by asset decile, {lab}\n" + m.round(2).to_string() + "\n")
    y07 = d[d["year"] == 2007].copy()
    y07["awlev"] = y07["leverage"] * y07["ta"] / y07["ta"].mean()
    top = y07[y07["awlev"] >= y07["awlev"].quantile(0.95)].sort_values("awlev", ascending=False)
    f.write("\nTop 5% asset-weighted leverage, 2007 (all regions)\n"
            + top[["name", "iso2", "leverage", "ta"]].head(25).to_string() + "\n")
print(open(f"{OUT}/stylized_facts_summary.txt").read())

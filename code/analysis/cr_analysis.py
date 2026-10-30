"""
Coimbra & Rey (2024 REStud) replication + FX extension on BankFocus panels.

Uses ONLY the global panel (TA >= USD 10bn in any year, worldwide). US results use the US banks
inside that panel.

Usage: python cr_analysis.py <global main csv> <ffr csv> <out_dir>

Figures
  G1  asset-weighted leverage quantiles (paper's Fig 1 definition): US 1997 = 100, global 2005 = 100
  G1b unweighted leverage quantiles: US 1997 = 100, global 2005 = 100
  G2  mean leverage by asset / equity decile (paper's Fig 2): US 1997-2007, global 2005-2007
  G3  share of assets held by the top-5% most levered banks vs real / nominal FFR (paper's Fig 3)
Regressions (paper's eq. 1, Table A1), bank FE, SE clustered by bank
  Lev_it = b1 Lev_i,t-1 + b2 FF_t + b3 Top5_it + b4 FF_t x Top5_it + a_i (+ year FE)
FX extension (global sample): add X_i,t-1 and its interactions with FF and Top5
  X = USD loan share, FX loan share, foreign-market loan share, FX-derivative notional / assets
"""
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
from linearmodels.panel import PanelOLS

GL, FFR, OUT = sys.argv[1:4]
C = {"blue": "#2a78d6", "orange": "#eb6834", "aqua": "#1baf7a", "yellow": "#eda100"}
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e4e3dd"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "lines.linewidth": 2,
                     "figure.dpi": 150})

ff = pd.read_csv(FFR).set_index("year")


def prep(path, min_year, max_year=2025):
    d = pd.read_csv(path, low_memory=False)
    d = d[(d["network_member"] == 0) & d["leverage"].notna() & (d["ta"] > 0)
          & d["year"].between(min_year, max_year)].copy()
    g = d.groupby("year")["leverage"]
    d["leverage"] = d["leverage"].clip(g.transform(lambda x: x.quantile(0.01)),
                                       g.transform(lambda x: x.quantile(0.99)))
    return d


gl_full = prep(GL, 1997)
us = gl_full[gl_full["iso2"] == "US"].copy()          # US banks in the global panel, 1997-2025
gl = gl_full[gl_full["year"] >= 2005].copy()          # all regions are covered from 2005


# ------------------------------------------------------------------ figures
def quantile_index(s, qs, base, weighted):
    s = s.copy()
    s["x"] = s["leverage"] * (s["ta"] / s.groupby("year")["ta"].transform("mean") if weighted else 1)
    q = s.groupby("year")["x"].quantile(qs).unstack()
    return q.div(q.loc[base]) * 100


def fig1(s, base, title, fname, weighted):
    idx = quantile_index(s, [0.05, 0.50, 0.90, 0.95], base, weighted)
    dense = quantile_index(s, [0.75, 0.80, 0.85, 0.90, 0.95, 0.99], base, weighted)
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
    for qv, lab, col in [(0.95, "Top 5%", C["blue"]), (0.90, "Top 10%", C["orange"]),
                         (0.50, "Median", C["aqua"]), (0.05, "Bottom 5%", C["yellow"])]:
        ax[0].plot(idx.index, idx[qv], color=col, label=lab)
    ax[0].set_title("Selected quantiles", loc="left", color=INK)
    for col, qv in zip(["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#104281"], dense.columns):
        ax[1].plot(dense.index, dense[qv], color=col, label=f"p{int(round(qv * 100))}")
    ax[1].set_title("Quantiles above the 75th", loc="left", color=INK)
    for a in ax:
        a.axhline(100, color=MUTED, lw=0.8, ls=":")
        a.axvspan(2007.5, 2009.5, color=GRID, alpha=0.6, lw=0)
        a.set_ylabel(f"Index ({base} = 100)")
        a.legend(frameon=False, fontsize=8, loc="upper left", bbox_to_anchor=(1.0, 1.0))
        a.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    fig.suptitle(title, x=0.01, ha="left", color=INK, fontsize=12)
    fig.tight_layout(); fig.savefig(f"{OUT}/{fname}", bbox_inches="tight"); plt.close(fig)
    return idx


def fig2(s, title, fname):
    s = s.copy()
    s["a_dec"] = pd.qcut(s["ta"], 10, labels=range(1, 11))
    s["e_dec"] = pd.qcut(s["te"], 10, labels=range(1, 11))
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    out = {}
    for a, key, lab in [(ax[0], "a_dec", "Asset decile"), (ax[1], "e_dec", "Equity decile")]:
        m = s.groupby(key, observed=True)["leverage"].mean()
        out[lab] = m
        a.plot(m.index.astype(int), m.values, "o-", color=C["blue"], ms=6, mfc="white", mew=2)
        a.set_xlabel(lab); a.set_xticks(range(1, 11))
    ax[0].set_ylabel("Mean leverage (assets / equity)")
    fig.suptitle(title, x=0.01, ha="left", color=INK, fontsize=12)
    fig.tight_layout(); fig.savefig(f"{OUT}/{fname}", bbox_inches="tight"); plt.close(fig)
    return pd.DataFrame(out)


def top5_share(s):
    def f(g):
        cut = g["leverage"].quantile(0.95)
        return g.loc[g["leverage"] >= cut, "ta"].sum() / g["ta"].sum()
    return s.groupby("year")[["leverage", "ta"]].apply(f)


def fig3(s, title, fname):
    sh = (top5_share(s) * 100).rename("share").to_frame().join(ff)
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for a, col, lab in [(ax[0], "ffr_real", "Real effective FFR (pp)"),
                        (ax[1], "ffr_nominal", "Nominal effective FFR (pp)")]:
        a.scatter(sh[col], sh["share"], s=36, color=C["blue"], edgecolor="white", linewidth=1.5, zorder=3)
        b = np.polyfit(sh[col], sh["share"], 1)
        xs = np.linspace(sh[col].min(), sh[col].max(), 50)
        a.plot(xs, np.polyval(b, xs), color=C["orange"], lw=1.5)
        for y, r in sh.iterrows():
            a.annotate(str(y)[2:], (r[col], r["share"]), xytext=(3, 3), textcoords="offset points",
                       fontsize=7, color=MUTED)
        rho = sh[[col, "share"]].corr().iloc[0, 1]
        a.set_xlabel(lab); a.set_title(f"corr = {rho:.2f}, slope = {b[0]:.2f}", loc="left", color=INK, fontsize=10)
    ax[0].set_ylabel("Assets of top-5% levered banks (% of total)")
    fig.suptitle(title, x=0.01, ha="left", color=INK, fontsize=12)
    fig.tight_layout(); fig.savefig(f"{OUT}/{fname}", bbox_inches="tight"); plt.close(fig)
    return sh


g1us = fig1(us, 1997, "Asset-weighted leverage by quantile — US banks in the global panel (1997 = 100)",
            "figG1_us_aw.png", True)
g1usu = fig1(us, 1997, "Leverage by quantile — US banks in the global panel, unweighted (1997 = 100)",
             "figG1b_us_unweighted.png", False)
g1 = fig1(gl, 2005, "Asset-weighted leverage by quantile — global banks (2005 = 100)", "figG1_global_aw.png", True)
g1b = fig1(gl, 2005, "Leverage by quantile — global banks, unweighted (2005 = 100)", "figG1b_global_unweighted.png",
           False)
g2us = fig2(us[us["year"] <= 2007], "Mean leverage by size and equity decile — US banks, 1997–2007",
            "figG2_us_deciles.png")
g2 = fig2(gl[gl["year"] <= 2007], "Mean leverage by size and equity decile — global, 2005–2007", "figG2_global_deciles.png")
g3us = fig3(us, "Top-5% levered banks' asset share vs Fed Funds — US banks, 1997–2025", "figG3_us.png")
g3gl = fig3(gl, "Top-5% levered banks' asset share vs Fed Funds — global banks, 2005–2025", "figG3_global.png")


# ------------------------------------------------------------------ regressions
def build(s, x=None):
    s = s.sort_values(["bvdid", "year"]).copy()
    s["aw"] = s["leverage"] * s["ta"] / s.groupby("year")["ta"].transform("mean")
    for q, nm in [(0.95, "top5"), (0.90, "top10")]:
        s[nm] = (s["leverage"] >= s.groupby("year")["leverage"].transform(lambda v: v.quantile(q))).astype(float)
    s["top5aw"] = (s["aw"] >= s.groupby("year")["aw"].transform(lambda v: v.quantile(0.95))).astype(float)
    prev = s[["bvdid", "year", "leverage"] + ([x] if x else [])].copy()
    prev["year"] += 1
    prev = prev.rename(columns={"leverage": "lev_l1", **({x: "x_l1"} if x else {})})
    s = s.merge(prev, on=["bvdid", "year"], how="inner")
    s = s.join(ff[["ffr_real", "ffr_nominal"]], on="year")
    s["FF"] = s["ffr_real"]
    for d in ["top5", "top10", "top5aw"]:
        s[f"FFx{d}"] = s["FF"] * s[d]
    if x:
        s = s[s["x_l1"].notna()].copy()
        s["FFxX"] = s["FF"] * s["x_l1"]
        s["top5xX"] = s["top5"] * s["x_l1"]
        s["FFxtop5xX"] = s["FF"] * s["top5"] * s["x_l1"]
    return s.set_index(["bvdid", "year"])


def fit(s, cols, time_fe=False):
    r = PanelOLS(s["leverage"], s[cols], entity_effects=True, time_effects=time_fe,
                 drop_absorbed=True, check_rank=False).fit(cov_type="clustered", cluster_entity=True)
    return r


LAB = {"lev_l1": "Lev$_{t-1}$", "FF": "Real FF", "top5": "Top5", "FFxtop5": "FF $\\times$ Top5",
       "top10": "Top10", "FFxtop10": "FF $\\times$ Top10", "top5aw": "Top5 (asset-wtd)",
       "FFxtop5aw": "FF $\\times$ Top5 (asset-wtd)", "x_l1": "$X_{t-1}$", "FFxX": "FF $\\times X_{t-1}$",
       "top5xX": "Top5 $\\times X_{t-1}$", "FFxtop5xX": "FF $\\times$ Top5 $\\times X_{t-1}$"}


def star(p):
    return "^{***}" if p < 0.01 else "^{**}" if p < 0.05 else "^{*}" if p < 0.1 else ""


def tex_table(results, heads, rows, caption, label, notes, fname):
    """Write an article-style table (booktabs + threeparttable) and keep it for the combined document."""
    lines = ["\\begin{table}[htbp]", "\\centering", "\\small", "\\begin{threeparttable}",
             f"\\caption{{{caption}}}", f"\\label{{{label}}}",
             "\\begin{tabular}{l" + "c" * len(results) + "}", "\\toprule",
             " & " + " & ".join(f"({i + 1})" for i in range(len(results))) + " \\\\",
             " & " + " & ".join(heads) + " \\\\", "\\midrule"]
    body = []
    for v in rows:
        b = [f"${r.params[v]:.3f}{star(r.pvalues[v])}$" if v in r.params.index else "" for r in results]
        se = [f"$({r.std_errors[v]:.3f})$" if v in r.params.index else "" for r in results]
        if any(b):
            body += [f"{LAB[v]} & " + " & ".join(b) + " \\\\", " & " + " & ".join(se) + " \\\\[2pt]"]
    if body:
        body[-1] = body[-1].replace("[2pt]", "")
    lines += body
    lines += ["\\midrule",
              "Bank FE & " + " & ".join("Yes" for _ in results) + " \\\\",
              "Year FE & " + " & ".join("Yes" if "Time" in str(r.included_effects) else "No" for r in results) + " \\\\",
              "Observations & " + " & ".join(f"{r.nobs:,}" for r in results) + " \\\\",
              "Banks & " + " & ".join(f"{int(r.entity_info['total']):,}" for r in results) + " \\\\",
              "Within $R^2$ & " + " & ".join(f"{r.rsquared_within:.3f}" for r in results) + " \\\\",
              "\\bottomrule", "\\end{tabular}",
              "\\begin{tablenotes}[flushleft]", "\\footnotesize", "\\item \\textit{Notes:} " + notes,
              "\\end{tablenotes}", "\\end{threeparttable}", "\\end{table}"]
    txt = "\n".join(lines) + "\n"
    open(f"{OUT}/{fname}", "w").write(txt)
    ALL_TABLES.append(txt)


ALL_TABLES = []
PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage{booktabs}
\usepackage{amsmath,amssymb}
\usepackage{caption}
\usepackage{threeparttable}
\usepackage[T1]{fontenc}
\usepackage{lmodern}
\captionsetup[table]{labelfont=bf, font=small, skip=6pt}
\begin{document}
"""


summary = []
base_cols = ["lev_l1", "FF", "top5", "FFxtop5"]
tabs = {}
for name, s, yrs in [("US banks, 1997–2015", us, (1997, 2015)),
                     ("US banks, 1997–2025", us, (1997, 2025)),
                     ("Global, 2005–2025", gl, (2005, 2025)),
                     ("Global ex-US, 2005–2025", gl[gl["iso2"] != "US"], (2005, 2025))]:
    d = build(s[s["year"].between(*yrs)])
    res = [fit(d, base_cols),
           fit(d, ["lev_l1", "top5", "FFxtop5"], time_fe=True),
           fit(d, ["lev_l1", "FF", "top5aw", "FFxtop5aw"]),
           fit(d, ["lev_l1", "FF", "top10", "FFxtop10"])]
    tabs[name] = res
    r0 = res[0]
    summary.append(f"{name}: N={r0.nobs}, banks={int(r0.entity_info['total'])}, "
                   f"FF={r0.params['FF']:.3f} (p={r0.pvalues['FF']:.3f}), "
                   f"FFxTop5={r0.params['FFxtop5']:.3f} (p={r0.pvalues['FFxtop5']:.3f}); "
                   f"with year FE FFxTop5={res[1].params['FFxtop5']:.3f} (p={res[1].pvalues['FFxtop5']:.3f}); "
                   f"AW FFxTop5aw={res[2].params['FFxtop5aw']:.3f} (p={res[2].pvalues['FFxtop5aw']:.3f}); "
                   f"Top10 FFxTop10={res[3].params['FFxtop10']:.3f} (p={res[3].pvalues['FFxtop10']:.3f})")

notes_base = ("Sample: BankFocus global panel (banks with total assets $\\geq$ USD 10bn in at least one year). "
              "Dependent variable: book leverage (total assets / total equity), winsorized at 1/99\\% by year. "
              "FF is the annual average effective Fed Funds rate minus annual-average CPI inflation (FRED FEDFUNDS, "
              "CPIAUCSL). Top5 (Top10) = 1 if the bank's leverage is in the top 5\\% (10\\%) of that year's "
              "cross-section; asset-weighted version ranks leverage $\\times$ assets/mean assets. Standard errors "
              "clustered by bank in parentheses. $^{*}p<0.1$, $^{**}p<0.05$, $^{***}p<0.01$. Specification follows "
              "Coimbra and Rey (2024), eq.~(1) and Table A1.")
heads = ["Baseline", "Year FE", "Top5 (AW)", "Top10"]
rows = ["lev_l1", "FF", "top5", "FFxtop5", "top5aw", "FFxtop5aw", "top10", "FFxtop10"]
for i, (name, res) in enumerate(tabs.items()):
    tex_table(res, heads, rows, f"Leverage and the real Fed Funds rate: {name.replace('–', '--')}", f"tab:cr_eq1_{i + 1}",
              notes_base, f"table_eq1_{i + 1}.tex")

# FX extension: global sample, year FE (FF main effect absorbed), interactions with X_{t-1}
fx_res, fx_heads = [], []
for x, lab in [("usd_loan_share", "USD loan sh."), ("fx_loan_share", "FX loan sh."),
               ("foreign_mkt_loan_share", "Foreign mkt sh."), ("fxder_notional_ta", "FX deriv./TA")]:
    s = gl.copy()
    if x == "fxder_notional_ta":
        lo, hi = s[x].quantile([0.01, 0.99]); s[x] = s[x].clip(lo, hi)
    d = build(s, x)
    r = fit(d, ["lev_l1", "top5", "FFxtop5", "x_l1", "FFxX", "top5xX", "FFxtop5xX"], time_fe=True)
    fx_res.append(r); fx_heads.append(lab)
    summary.append(f"FX ext X={x}: N={r.nobs}, banks={int(r.entity_info['total'])}, "
                   f"FFxX={r.params['FFxX']:.3f} (p={r.pvalues['FFxX']:.3f}), "
                   f"FFxTop5xX={r.params['FFxtop5xX']:.3f} (p={r.pvalues['FFxtop5xX']:.3f}), "
                   f"FFxTop5={r.params['FFxtop5']:.3f} (p={r.pvalues['FFxtop5']:.3f})")
tex_table(fx_res, fx_heads, ["lev_l1", "top5", "FFxtop5", "x_l1", "FFxX", "top5xX", "FFxtop5xX"],
          "FX exposure and the sensitivity of leverage to the Fed Funds rate (global banks, 2005--2025)",
          "tab:cr_fx", notes_base.replace("Specification follows", "Baseline specification follows") +
          " $X_{t-1}$ is the lagged exposure measure named in the column header; year fixed effects absorb the "
          "FF main effect. FX derivative notional / assets winsorized at 1/99\\%.", "table_fx_extension.tex")

with open(f"{OUT}/cr_tables.tex", "w") as f:
    f.write(PREAMBLE + "\n\\clearpage\n\n".join(ALL_TABLES) + "\n\\end{document}\n")

with open(f"{OUT}/analysis_summary.txt", "w") as f:
    f.write("=== Fig G1 US AW index (1997=100)\n" + g1us.round(1).to_string() + "\n")
    f.write("\n=== Fig G1b US unweighted (1997=100)\n" + g1usu.round(1).to_string() + "\n")
    f.write("\n=== Fig G1 global AW index (2005=100)\n" + g1.round(1).to_string() + "\n")
    f.write("\n=== Fig G1b global unweighted (2005=100)\n" + g1b.round(1).to_string() + "\n")
    f.write("\n=== Fig G2 US 1997-2007 mean leverage by decile\n" + g2us.round(2).to_string() + "\n")
    f.write("\n=== Fig G2 global 2005-2007 mean leverage by decile\n" + g2.round(2).to_string() + "\n")
    f.write("\n=== Fig G3 US top-5% asset share vs FFR\n" + g3us.round(3).to_string() + "\n")
    f.write("\n=== Fig G3 global top-5% asset share vs FFR\n" + g3gl.round(3).to_string() + "\n")
    f.write("\n=== Regressions\n" + "\n".join(summary) + "\n")
print(open(f"{OUT}/analysis_summary.txt").read())

"""
Regional / country heterogeneity in Coimbra & Rey Figure 1 around the GFC, and pre-crisis
concentration of assets and equity. Global panel only.

Usage: python region_gfc.py <global_panel_main.csv> <out_dir>

Design
  * leverage winsorized 1/99% by year (whole panel); French network members dropped
  * base year 2006 (Europe coverage jumps 2005 -> 2006, China from 2005 -> 2013)
  * MAIN = constant-composition sample: banks observed in every year 2006-2012 within the group
  * groups: 8 regions + Europe split (core / periphery GIIPS / UK) + countries with >= 18 balanced banks
GFC metrics (balanced 2006-2012, unweighted quantiles, 2006 = 100)
  build-up   = max(index 2007, 2008) - 100            (pre-crisis leverage expansion)
  delever    = index 2012 - max(index 2007, 2008)     (post-crisis deleveraging)
Concentration (2006, same balanced sample)
  CR5 / HHI of assets and of equity, asset share of top-10% most levered banks,
  Spearman(size, leverage), mean leverage top asset decile / bottom decile (size gradient)
"""
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker

SRC, OUT = sys.argv[1], sys.argv[2]
C = {"blue": "#2a78d6", "orange": "#eb6834", "aqua": "#1baf7a", "yellow": "#eda100"}
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e4e3dd"
plt.rcParams.update({"font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "lines.linewidth": 1.8,
                     "figure.dpi": 150})

d = pd.read_csv(SRC, low_memory=False)
d = d[(d["network_member"] == 0) & d["leverage"].notna() & (d["ta"] > 0) & (d["te"] > 0)].copy()
g = d.groupby("year")["leverage"]
d["leverage"] = d["leverage"].clip(g.transform(lambda x: x.quantile(0.01)), g.transform(lambda x: x.quantile(0.99)))

PERIPH = {"IT", "ES", "PT", "GR", "IE"}
CORE = {"DE", "FR", "NL", "AT", "BE", "LU", "CH", "FI", "SE", "DK", "NO", "IS", "LI", "MC"}
d["eu_group"] = np.where(d["iso2"] == "GB", "UK",
                np.where(d["iso2"].isin(PERIPH), "Europe periphery (GIIPS)",
                np.where(d["iso2"].isin(CORE), "Europe core", None)))

REGIONS = ["North America", "Europe", "Japan & Developed Asia-Pacific", "China", "Emerging Asia",
           "Latin America", "Middle East & Africa", "Emerging Europe & CIS"]
SHORT = {"North America": "N. America", "Europe": "Europe", "Japan & Developed Asia-Pacific": "Japan & Dev. AP",
         "China": "China", "Emerging Asia": "Emerging Asia", "Latin America": "Latin America",
         "Middle East & Africa": "M. East & Africa", "Emerging Europe & CIS": "Emerging Eur. & CIS",
         "Europe core": "Europe core", "Europe periphery (GIIPS)": "Europe periphery", "UK": "UK"}
COUNTRY_NAMES = {"US": "United States", "DE": "Germany", "JP": "Japan", "CH": "Switzerland", "IT": "Italy",
                 "GB": "United Kingdom", "CA": "Canada", "FR": "France", "TW": "Taiwan", "CN": "China",
                 "AT": "Austria"}


def groups(frame):
    out = {r: frame[frame["region"] == r] for r in REGIONS}
    for eg in ["Europe core", "Europe periphery (GIIPS)", "UK"]:
        out[eg] = frame[frame["eu_group"] == eg]
    return out


def balanced(frame, y0=2006, y1=2012):
    w = frame[frame["year"].between(y0, y1)]
    n = w.groupby("bvdid")["year"].nunique()
    return w[w["bvdid"].isin(n[n == (y1 - y0 + 1)].index)]


def qindex(frame, qs, base=2006, weighted=False):
    f = frame.copy()
    f["x"] = f["leverage"] * (f["ta"] / f.groupby("year")["ta"].transform("mean") if weighted else 1)
    q = f.groupby("year")["x"].quantile(qs).unstack()
    return q.div(q.loc[base]) * 100


QSTYLE = {0.95: ("p95", C["blue"]), 0.90: ("p90", C["orange"]), 0.50: ("Median", C["aqua"]),
          0.10: ("p10", "#8a8986"), 0.05: ("p5", C["yellow"])}


def small_multiples(items, qs, title, fname, xlim, ncol=4, base=2006, weighted=False):
    n = len(items)
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.2 * ncol, 2.6 * nrow), sharex=True)
    axes = np.atleast_1d(axes).ravel()
    out = {}
    for ax, (lab, frame) in zip(axes, items):
        idx = qindex(frame, qs, base, weighted)
        out[lab] = idx
        for q in qs:
            nm, col = QSTYLE[q]
            ax.plot(idx.index, idx[q], color=col, label=nm)
        nb = frame[frame["year"] == base]["bvdid"].nunique()
        ax.set_title(f"{lab}  (n={nb})", loc="left", fontsize=9, color=INK)
        ax.axhline(100, color=MUTED, lw=0.7, ls=":")
        ax.axvspan(2007.5, 2009.5, color=GRID, alpha=0.7, lw=0)
        ax.set_xlim(*xlim)
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(4, integer=True))
    for ax in axes[n:]:
        ax.axis("off")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper right", ncol=len(qs), frameon=False, fontsize=8, bbox_to_anchor=(1.0, 1.0))
    fig.suptitle(title, x=0.01, ha="left", color=INK, fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(f"{OUT}/{fname}", bbox_inches="tight")
    plt.close(fig)
    return out


def hhi(s):
    sh = s / s.sum()
    return float((sh ** 2).sum())


def concentration(frame):
    """frame: one cross-section"""
    a = frame["ta"].sort_values(ascending=False)
    e = frame["te"].sort_values(ascending=False)
    lev_cut = frame["leverage"].quantile(0.90)
    dec = pd.qcut(frame["ta"], 10, labels=False, duplicates="drop")
    m = frame.groupby(dec)["leverage"].mean()
    return {
        "n_banks": len(frame),
        "cr5_assets": a.head(5).sum() / a.sum(),
        "cr5_equity": e.head(5).sum() / e.sum(),
        "hhi_assets": hhi(frame["ta"]),
        "hhi_equity": hhi(frame["te"]),
        "top10lev_asset_share": frame.loc[frame["leverage"] >= lev_cut, "ta"].sum() / frame["ta"].sum(),
        "spearman_size_lev": frame["ta"].rank().corr(frame["leverage"].rank()),
        "size_gradient": m.iloc[-1] / m.iloc[0],
        "median_lev": frame["leverage"].median(),
        "awlev": np.average(frame["leverage"], weights=frame["ta"]),
    }


def gfc_metrics(idx):
    peak_q = {}
    for q in idx.columns:
        pk = max(idx.loc[2007, q], idx.loc[2008, q])
        peak_q[q] = (pk - 100, idx.loc[2012, q] - pk)
    return peak_q


# ---------------------------------------------------------------- figures
reg_all = groups(d)
reg_bal = {k: balanced(v) for k, v in reg_all.items()}
ctry = [c for c in COUNTRY_NAMES]
ctry_bal = {COUNTRY_NAMES[c]: balanced(d[d["iso2"] == c]) for c in ctry}

R1 = small_multiples([(SHORT[r], reg_all[r]) for r in REGIONS], [0.95, 0.90, 0.50, 0.05],
                     "Leverage quantiles by region, unweighted, all banks (2006 = 100)", "figR1_regions_all.png",
                     (2005.5, 2025.5))
R2 = small_multiples([(SHORT[r], reg_bal[r]) for r in REGIONS], [0.95, 0.90, 0.50, 0.05],
                     "Leverage quantiles by region around the GFC — constant sample of banks observed 2006–2012 (2006 = 100)",
                     "figR2_regions_balanced_gfc.png", (2005.8, 2012.2))
R2e = small_multiples([(SHORT[r], reg_bal[r]) for r in ["Europe core", "Europe periphery (GIIPS)", "UK"]],
                      [0.90, 0.50, 0.10],
                      "Europe split around the GFC and euro crisis — constant sample 2006–2012 (2006 = 100)",
                      "figR2b_europe_split_gfc.png", (2005.8, 2012.2), ncol=3)
R2w = small_multiples([(SHORT[r], reg_bal[r]) for r in REGIONS], [0.95, 0.90, 0.50, 0.05],
                      "Asset-weighted leverage quantiles by region — constant sample 2006–2012 (2006 = 100)",
                      "figR2c_regions_balanced_aw.png", (2005.8, 2012.2), weighted=True)
R3 = small_multiples(list(ctry_bal.items()), [0.90, 0.50, 0.10],
                     "Leverage quantiles by country around the GFC — constant sample 2006–2012 (2006 = 100)",
                     "figR3_countries_balanced_gfc.png", (2005.8, 2012.2))

# ---------------------------------------------------------------- GFC metrics + concentration table
rows = []
for kind, items in [("Region", [(r, reg_bal[r]) for r in REGIONS]),
                    ("Europe split", [(r, reg_bal[r]) for r in ["Europe core", "Europe periphery (GIIPS)", "UK"]]),
                    ("Country", list(ctry_bal.items()))]:
    for lab, frame in items:
        hi = 0.95 if kind == "Region" else 0.90
        idx = qindex(frame, [hi, 0.50], 2006)
        gm = gfc_metrics(idx)
        conc = concentration(frame[frame["year"] == 2006])
        rows.append({"kind": kind, "group": SHORT.get(lab, lab), "top_q": f"p{int(hi * 100)}",
                     "buildup_top": gm[hi][0], "delever_top": gm[hi][1],
                     "buildup_med": gm[0.50][0], "delever_med": gm[0.50][1], **conc})
tab = pd.DataFrame(rows)
tab.to_csv(f"{OUT}/region_gfc_metrics.csv", index=False)

# concentration over time (all banks per region, unbalanced) for context
ct = []
for r in REGIONS + ["Europe core", "Europe periphery (GIIPS)", "UK"]:
    fr = reg_all[r]
    for y, cs in fr.groupby("year"):
        if y < 2005 or len(cs) < 10:
            continue
        ct.append({"group": SHORT[r], "year": y, **concentration(cs)})
ct = pd.DataFrame(ct)
ct.to_csv(f"{OUT}/region_concentration_by_year.csv", index=False)

# ---------------------------------------------------------------- scatter: pre-crisis structure vs GFC dynamics
sc = pd.concat([tab[(tab["kind"] == "Region") & (tab["group"] != "Europe")],
                tab[tab["kind"] == "Europe split"].assign(kind="Region"),
                tab[(tab["kind"] == "Country") & (tab["group"] != "United Kingdom")]])
fig, ax = plt.subplots(2, 3, figsize=(13, 7.5))
pairs = [("cr5_assets", "CR5 of assets, 2006"), ("cr5_equity", "CR5 of equity, 2006"),
         ("median_lev", "Median leverage, 2006")]
for j, (xv, xl) in enumerate(pairs):
    for i, (yv, yl) in enumerate([("buildup_top", "Build-up of top quantile, 2006→peak 07/08 (index pts)"),
                                   ("delever_top", "Deleveraging of top quantile, peak→2012 (index pts)")]):
        a = ax[i, j]
        for kind, col, mk in [("Region", C["blue"], "o"), ("Country", C["orange"], "s")]:
            s = sc[sc["kind"] == kind]
            a.scatter(s[xv], s[yv], color=col, marker=mk, s=40, edgecolor="white", linewidth=1.2, zorder=3,
                      label={"Region": "Regions (p95; Europe split p90)", "Country": "Countries (p90)"}[kind])
            for _, r in s.iterrows():
                a.annotate(r["group"], (r[xv], r[yv]), xytext=(3, 3), textcoords="offset points", fontsize=6.5,
                           color=MUTED)
        rho = sc[[xv, yv]].corr(method="spearman").iloc[0, 1]
        a.set_title(f"Spearman ρ = {rho:.2f}", loc="left", fontsize=9, color=INK)
        a.axhline(0, color=MUTED, lw=0.7, ls=":")
        if i == 1:
            a.set_xlabel(xl)
        if j == 0:
            a.set_ylabel(yl, fontsize=8)
ax[0, 0].legend(frameon=False, fontsize=8, loc="upper left")
fig.suptitle("Pre-crisis structure vs leverage dynamics of the most levered banks around the GFC "
             "(Europe shown as core / periphery / UK)",
             x=0.01, ha="left", color=INK, fontsize=11)
fig.tight_layout(rect=(0, 0, 1, 0.96))
fig.savefig(f"{OUT}/figR4_concentration_vs_gfc.png", bbox_inches="tight")
plt.close(fig)

# concentration time series
fig, ax = plt.subplots(1, 3, figsize=(13, 4))
pal = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#7a5cc7", "#6b6a64"]
for col, r in zip(pal, REGIONS):
    s = ct[ct["group"] == SHORT[r]].set_index("year")
    for a, v in zip(ax, ["cr5_assets", "cr5_equity", "top10lev_asset_share"]):
        a.plot(s.index, s[v] * 100, color=col, label=SHORT[r], lw=1.6)
for a, t in zip(ax, ["CR5 of assets (%)", "CR5 of equity (%)", "Asset share of top-10% levered banks (%)"]):
    a.set_title(t, loc="left", fontsize=9, color=INK)
    a.axvspan(2007.5, 2009.5, color=GRID, alpha=0.7, lw=0)
    a.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(5, integer=True))
ax[2].legend(frameon=False, fontsize=7.5, loc="upper left", bbox_to_anchor=(1.0, 1.0))
fig.suptitle("Concentration of assets and equity within each region, all banks in the panel",
             x=0.01, ha="left", color=INK, fontsize=11)
fig.tight_layout(rect=(0, 0, 1, 0.94))
fig.savefig(f"{OUT}/figR5_concentration_timeseries.png", bbox_inches="tight")
plt.close(fig)

# ---------------------------------------------------------------- LaTeX table
def f(x, p=1):
    return f"{x:.{p}f}"


lines = [r"\begin{table}[htbp]", r"\centering", r"\footnotesize", r"\begin{threeparttable}",
         r"\caption{Leverage dynamics around the GFC and pre-crisis concentration, by region and country}",
         r"\label{tab:region_gfc}", r"\setlength{\tabcolsep}{4pt}",
         r"\begin{tabular}{lrrrrrrrrrrr}", r"\toprule",
         r" & & \multicolumn{2}{c}{Top quantile} & \multicolumn{2}{c}{Median} & \multicolumn{6}{c}{Structure in 2006} \\",
         r"\cmidrule(lr){3-4}\cmidrule(lr){5-6}\cmidrule(lr){7-12}",
         r" & Banks & Build-up & Delever. & Build-up & Delever. & CR5 $A$ & CR5 $E$ & Top10\%-lev $A$ sh. & $\rho$(size, lev) & Lev. D10/D1 & Median lev. \\",
         r"\midrule"]
for kind in ["Region", "Europe split", "Country"]:
    lab_k = {"Region": "Regions (top = p95)", "Europe split": "Europe split (top = p90)", "Country": "Countries (top = p90)"}[kind]
    lines.append(rf"\multicolumn{{12}}{{l}}{{\textit{{{lab_k}}}}} \\")
    for _, r in tab[tab["kind"] == kind].iterrows():
        lines.append(f"{r['group'].replace('&', chr(92) + '&')} & {int(r['n_banks'])} & {f(r['buildup_top'])} & {f(r['delever_top'])} & "
                     f"{f(r['buildup_med'])} & {f(r['delever_med'])} & {f(100 * r['cr5_assets'])} & "
                     f"{f(100 * r['cr5_equity'])} & {f(100 * r['top10lev_asset_share'])} & "
                     f"{f(r['spearman_size_lev'], 2)} & {f(r['size_gradient'], 2)} & {f(r['median_lev'])} \\\\")
lines += [r"\bottomrule", r"\end{tabular}", r"\begin{tablenotes}[flushleft]", r"\footnotesize",
          r"\item \textit{Notes:} BankFocus global panel (banks with total assets $\geq$ USD 10bn in at least one year), "
          r"constant sample of banks observed in every year 2006--2012 within each group; French mutualist network "
          r"members excluded; leverage = total assets / total equity, winsorized at 1/99\% by year. Unweighted leverage "
          r"quantiles indexed to 2006 = 100. Build-up = $\max(I_{2007}, I_{2008}) - 100$; Delever. = $I_{2012} - \max(I_{2007}, I_{2008})$ "
          r"(index points). Top quantile is p95 for regions, p90 for the Europe split and countries (fewer banks). CR5 $A$ ($E$): share of "
          r"the five largest banks in total assets (equity), \%. Top10\%-lev $A$ sh.: asset share of the 10\% most levered banks, \%. "
          r"$\rho$(size, lev): Spearman correlation of assets and leverage. Lev. D10/D1: mean leverage in the top over the bottom "
          r"asset decile. Median lev.: median leverage. All structure measures in 2006. Europe core = DE, FR, NL, AT, BE, LU, CH and Nordics; periphery = IT, ES, PT, GR, IE.",
          r"\end{tablenotes}", r"\end{threeparttable}", r"\end{table}"]
table_tex = "\n".join(lines) + "\n"
open(f"{OUT}/table_region_gfc.tex", "w").write(table_tex)
open(f"{OUT}/region_gfc_tables.tex", "w").write(
    "\\documentclass[11pt]{article}\n\\usepackage[margin=0.8in,landscape]{geometry}\n\\usepackage{booktabs}\n"
    "\\usepackage{amsmath,amssymb}\n\\usepackage{caption}\n\\usepackage{threeparttable}\n\\usepackage[T1]{fontenc}\n"
    "\\usepackage{lmodern}\n\\captionsetup[table]{labelfont=bf, font=small, skip=6pt}\n\\begin{document}\n"
    + table_tex + "\\end{document}\n")

pd.set_option("display.width", 220)
print(tab.round(3).to_string(index=False))


# ---------------------------------------------------------------- decomposition + base-year robustness
def decomp(frame, y0=2006, peak=2008, y1=2012):
    """log growth of total assets and equity for banks in the top decile of y0 leverage vs the rest"""
    b0 = frame[frame["year"] == y0]
    top = set(b0.loc[b0["leverage"] >= b0["leverage"].quantile(0.90), "bvdid"])
    res = {}
    for grp, ids in [("top", top), ("rest", set(b0["bvdid"]) - top)]:
        s = frame[frame["bvdid"].isin(ids)].groupby("year")[["ta", "te"]].sum()
        for a, b, lab in [(y0, peak, "pre"), (peak, y1, "post")]:
            res[f"{grp}_dlogA_{lab}"] = 100 * np.log(s.loc[b, "ta"] / s.loc[a, "ta"])
            res[f"{grp}_dlogE_{lab}"] = 100 * np.log(s.loc[b, "te"] / s.loc[a, "te"])
    return res


drows = []
for kind, items in [("Region", [(r, reg_bal[r]) for r in REGIONS]),
                    ("Europe split", [(r, reg_bal[r]) for r in ["Europe core", "Europe periphery (GIIPS)", "UK"]]),
                    ("Country", list(ctry_bal.items()))]:
    for lab, frame in items:
        drows.append({"kind": kind, "group": SHORT.get(lab, lab), **decomp(frame)})
dec = pd.DataFrame(drows)
dec.to_csv(f"{OUT}/region_gfc_decomposition.csv", index=False)

rob = []
for kind, items in [("Region", REGIONS), ("Europe split", ["Europe core", "Europe periphery (GIIPS)", "UK"])]:
    for r in items:
        fr = balanced(reg_all[r], 2005, 2012)
        if fr["bvdid"].nunique() < 15:
            continue
        hq = 0.95 if kind == "Region" else 0.90
        idx = qindex(fr, [hq, 0.50], 2005)
        gm = gfc_metrics(idx)
        rob.append({"kind": kind, "group": SHORT[r], "n_banks_2005bal": fr["bvdid"].nunique(), "top_q": f"p{int(hq*100)}",
                    "buildup_top_from2005": gm[hq][0], "delever_top": gm[hq][1],
                    "buildup_med_from2005": gm[0.50][0]})
for c, nm in COUNTRY_NAMES.items():
    fr = balanced(d[d["iso2"] == c], 2005, 2012)
    if fr["bvdid"].nunique() < 15:
        continue
    idx = qindex(fr, [0.90, 0.50], 2005)
    gm = gfc_metrics(idx)
    rob.append({"kind": "Country", "group": nm, "n_banks_2005bal": fr["bvdid"].nunique(),
                "top_q": "p90", "buildup_top_from2005": gm[0.90][0], "delever_top": gm[0.90][1],
                "buildup_med_from2005": gm[0.50][0]})
rob = pd.DataFrame(rob)
rob.to_csv(f"{OUT}/region_gfc_base2005_robustness.csv", index=False)
print(dec.round(1).to_string(index=False))
print(rob.round(1).to_string(index=False))


# ---------------------------------------------------------------- split windows (avoid dropping banks that failed in the GFC)
def split_metrics(frame, hi):
    pre = balanced(frame, 2006, 2008)
    post = balanced(frame, 2008, 2012)
    out = {"n_pre": pre["bvdid"].nunique(), "n_post": post["bvdid"].nunique()}
    if out["n_pre"] >= 15:
        ip = qindex(pre, [hi, 0.50], 2006)
        out["buildup_top_split"] = max(ip.loc[2007, hi], ip.loc[2008, hi]) - 100
        out["buildup_med_split"] = max(ip.loc[2007, 0.50], ip.loc[2008, 0.50]) - 100
    if out["n_post"] >= 15:
        iq = qindex(post, [hi, 0.50], 2008)
        out["delever_top_split"] = iq.loc[2012, hi] - 100
        out["delever_med_split"] = iq.loc[2012, 0.50] - 100
    return out


srows = []
for kind, items in [("Region", [(r, reg_all[r]) for r in REGIONS]),
                    ("Europe split", [(r, reg_all[r]) for r in ["Europe core", "Europe periphery (GIIPS)", "UK"]]),
                    ("Country", [(COUNTRY_NAMES[c], d[d["iso2"] == c]) for c in COUNTRY_NAMES])]:
    for lab, frame in items:
        hi = 0.95 if kind == "Region" else 0.90
        srows.append({"kind": kind, "group": SHORT.get(lab, lab), **split_metrics(frame, hi)})
split = pd.DataFrame(srows)
split.to_csv(f"{OUT}/region_gfc_split_windows.csv", index=False)
print(split.round(1).to_string(index=False))



# ---------------------------------------------------------------- Table 2: split windows + asset/equity decomposition
t2 = tab[["kind", "group"]].merge(split, on=["kind", "group"]).merge(dec, on=["kind", "group"])
L = [r"\begin{table}[htbp]", r"\centering", r"\footnotesize", r"\begin{threeparttable}",
     r"\caption{Robustness and decomposition: build-up and deleveraging by region and country}",
     r"\label{tab:region_gfc_decomp}", r"\setlength{\tabcolsep}{4pt}",
     r"\begin{tabular}{lrrrrrrrrrr}", r"\toprule",
     r" & \multicolumn{4}{c}{Split windows (index pts)} & \multicolumn{4}{c}{Top-decile banks (log pts)} & \multicolumn{2}{c}{Other banks (log pts)} \\",
     r"\cmidrule(lr){2-5}\cmidrule(lr){6-9}\cmidrule(lr){10-11}",
     r" & Banks & Banks & Build-up & Delever. & $\Delta A$ & $\Delta E$ & $\Delta A$ & $\Delta E$ & $\Delta A$ & $\Delta E$ \\",
     r" & 06--08 & 08--12 & top & top & 06--08 & 06--08 & 08--12 & 08--12 & 06--08 & 06--08 \\",
     r"\midrule"]


def g_(x, p=1):
    return "--" if pd.isna(x) else f"{x:.{p}f}"


for kind in ["Region", "Europe split", "Country"]:
    L.append(rf"\multicolumn{{11}}{{l}}{{\textit{{{kind}}}}} \\")
    for _, r in t2[t2["kind"] == kind].iterrows():
        L.append(f"{r['group'].replace('&', chr(92) + '&')} & {int(r['n_pre'])} & {int(r['n_post'])} & {g_(r.get('buildup_top_split'))} & "
                 f"{g_(r.get('delever_top_split'))} & {g_(r['top_dlogA_pre'])} & {g_(r['top_dlogE_pre'])} & "
                 f"{g_(r['top_dlogA_post'])} & {g_(r['top_dlogE_post'])} & {g_(r['rest_dlogA_pre'])} & "
                 f"{g_(r['rest_dlogE_pre'])} \\\\")
L += [r"\bottomrule", r"\end{tabular}", r"\begin{tablenotes}[flushleft]", r"\footnotesize",
      r"\item \textit{Notes:} Split windows: build-up uses banks observed in every year 2006--2008 (so banks that failed or "
      r"were absorbed after 2008 are kept), $\max(I_{2007}, I_{2008}) - 100$ with 2006 = 100; deleveraging uses banks observed "
      r"in every year 2008--2012, $I_{2012} - 100$ with 2008 = 100. Top quantile = p95 for regions, p90 for the Europe split "
      r"and countries; groups with fewer than 15 banks are not reported. Decomposition: within the 2006--2012 constant sample, "
      r"banks in the top decile of 2006 leverage vs all others; $\Delta A$, $\Delta E$ are $100\times$ log changes of the "
      r"group's summed total assets and equity (USD at closing-date exchange rates). Leverage rises when $\Delta A > \Delta E$.",
      r"\end{tablenotes}", r"\end{threeparttable}", r"\end{table}"]
table2 = "\n".join(L) + "\n"
open(f"{OUT}/table_region_gfc_decomp.tex", "w").write(table2)
open(f"{OUT}/region_gfc_tables.tex", "w").write(
    "\\documentclass[11pt]{article}\n\\usepackage[margin=0.8in,landscape]{geometry}\n\\usepackage{booktabs}\n"
    "\\usepackage{amsmath,amssymb}\n\\usepackage{caption}\n\\usepackage{threeparttable}\n\\usepackage[T1]{fontenc}\n"
    "\\usepackage{lmodern}\n\\captionsetup[table]{labelfont=bf, font=small, skip=6pt}\n\\begin{document}\n"
    + table_tex + "\n\\clearpage\n\n" + table2 + "\\end{document}\n")

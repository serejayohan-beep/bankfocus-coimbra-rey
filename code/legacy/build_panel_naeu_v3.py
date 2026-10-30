"""
Build a clean bank-year panel from BankFocus list exports (bankfocus_v2_part1..5.xlsx).

Input: bankfocus_v3_part1..6.xlsx
Usage:  python build_panel.py <folder_with_xlsx> <output_folder>

Outputs
  bankfocus_panel_all.csv / .dta : every bank-statement-year, with cleaning flags
  bankfocus_panel_main.csv / .dta: one obs per bank-year, main sample (keep_main==1)
  coverage_by_year.csv           : obs counts by year x region
Cleaning rules (see README section in the chat for rationale)
  1. 'n.a.' -> missing; 2026 dropped (almost empty)
  2. RWA/TA == 0 and capital ratios == 0 -> missing (BvD fills missing with 0)
  3. One statement per BvD ID x year, priority C1 > C2 > U1 > C* > U2 > U*
     ties (several C* statements) -> IFRS > US GAAP > Local GAAP, then most non-missing vars
  4. Flag subsidiaries whose Global Ultimate Owner is another bank in the sample (double counting)
  5. leverage = total assets / total equity; equity <= 0 -> leverage missing
  6. Flag balance-sheet identity gaps |A - L - E| / A > 2%
"""
import sys, glob, re
import numpy as np
import pandas as pd
from python_calamine import CalamineWorkbook

SRC = sys.argv[1] if len(sys.argv) > 1 else "."
OUT = sys.argv[2] if len(sys.argv) > 2 else "."

# short variable names: label prefix in BankFocus header -> name
VARMAP = {
    "Total assets": "ta",
    "Total equity": "te",
    "Total liabilities": "tl",
    "Total customer deposits": "cust_dep",
    "Deposits and short-term funding": "dep_stf",
    "Short-term wholesale funding": "st_wsf",
    "P/L for period [=Net income]": "ni",
    "Return on average assets (ROAA)": "roaa",
    "Gross loans & advances to customers": "gross_loans",
    "Impaired loans / Gross customer loans & advances": "npl_ratio",
    "Loans loss reserves": "llr",
    "Net impairment charges on loans & advances": "llp",
    "Tier 1 ratio (as reported)": "tier1",
    "Total capital adequacy ratio (as reported)": "car",
    "Risk-weighted asset intensity (RWA / Total Assets)": "rwa_ta",
    "Liquid assets / Total assets": "liq_ta",
    "Liquid assets / Deposits & short-term funding": "liq_dstf",
    "Closing date": "closing_date",
    "Accounting practice": "acc_practice",
}
IDMAP = {
    "Company name Latin alphabet": "name",
    "BvD ID number": "bvdid",
    "GUO - BvD ID number": "guo_bvdid",
    "Country ISO code": "iso2",
    "Consolidation code": "conscode",
    "Specialisation": "special",
    "Status": "status",
    "Status date": "status_date",
    "Inactive": "inactive",
    "Quoted": "listed",
    "Sifi": "sifi",
    "Branch": "branch",
    "NACE Rev. 2, core code (4 digits)": "nace",
    "Last avail. year": "last_year",
}
TEXTVARS = {"closing_date", "acc_practice"}

NORTH_AMERICA = {"US", "CA"}
MAIN_SPECIAL = {
    "Commercial bank", "Savings bank", "Cooperative bank", "Bank holding company",
    "Real estate & mortgage finance institution", "Investment bank",
}
CONS_PRIORITY = {"C1": 1, "C2": 2, "U1": 3, "C*": 4, "U2": 5, "U*": 6}
ACC_PRIORITY = {"IFRS": 1, "US GAAP": 2, "Local GAAP": 3}


def read_part(path, part):
    rows = CalamineWorkbook.from_path(path).get_sheet_by_name("Results").to_python()
    df = pd.DataFrame(rows[2:], columns=rows[0])
    df = df[df["BvD ID number"].astype(str).str.strip() != ""].copy()
    df["part"] = part
    return df


files = sorted(glob.glob(f"{SRC}/*part*.xlsx"), key=lambda f: re.search(r"part(\d+)", f).group(1))
wide = pd.concat([read_part(f, i + 1) for i, f in enumerate(files)], ignore_index=True)
print(f"read {len(files)} files, {len(wide)} statement rows, {wide['BvD ID number'].nunique()} BvD IDs")
wide["sid"] = np.arange(len(wide))  # statement id = one export row

# ---------- wide -> long ----------
pat = re.compile(r"^(.*?)\s+(?:th USD\s+)?(\d{4})$")
pieces = []
for col in wide.columns:
    m = pat.match(str(col))
    if not m or m.group(1) not in VARMAP:
        continue
    var, year = VARMAP[m.group(1)], int(m.group(2))
    s = wide[col].replace({"n.a.": np.nan, "": np.nan})
    if var not in TEXTVARS:
        s = pd.to_numeric(s, errors="coerce")
    pieces.append(pd.DataFrame({"sid": wide["sid"], "year": year, "var": var, "val": s}))
long = pd.concat(pieces).dropna(subset=["val"])
num = long[~long["var"].isin(TEXTVARS)].pivot_table(index=["sid", "year"], columns="var", values="val", aggfunc="first").astype(float)
txt = long[long["var"].isin(TEXTVARS)].pivot_table(index=["sid", "year"], columns="var", values="val", aggfunc="first")
panel = num.join(txt, how="left").reset_index()
panel = panel[panel["ta"].notna() & (panel["year"] <= 2025)]

ids = wide[list(IDMAP) + ["sid", "part"]].rename(columns=IDMAP)
ids["status_date"] = pd.to_datetime(ids["status_date"].replace("", np.nan), errors="coerce")
ids.loc[ids["status_date"].dt.year < 1950, "status_date"] = pd.NaT  # 1900-01-02 placeholder
ids["guo_bvdid"] = ids["guo_bvdid"].replace("", np.nan)
panel = panel.merge(ids, on="sid", how="left")
panel["closing_date"] = pd.to_datetime(panel["closing_date"], errors="coerce")
panel["fye_month"] = panel["closing_date"].dt.month

# ---------- value cleaning ----------
for v in ["rwa_ta", "tier1", "car"]:
    panel.loc[panel[v] == 0, v] = np.nan

# ---------- one statement per bank-year ----------
valvars = [v for v in VARMAP.values() if v not in TEXTVARS and v in panel]
panel["n_nonmiss"] = panel[valvars].notna().sum(axis=1)
panel["cons_rank"] = panel["conscode"].map(CONS_PRIORITY).fillna(9)
panel["acc_rank"] = panel["acc_practice"].map(ACC_PRIORITY).fillna(9)
panel = panel.sort_values(["bvdid", "year", "cons_rank", "acc_rank", "n_nonmiss"],
                          ascending=[True, True, True, True, False])
panel["chosen"] = (~panel.duplicated(["bvdid", "year"])).astype(int)

# ---------- parent/subsidiary double counting ----------
panel["main_special"] = panel["special"].isin(MAIN_SPECIAL).astype(int)
panel["is_branch"] = (panel["branch"] == "Yes").astype(int)
eligible_parent = set(panel.loc[(panel["main_special"] == 1) & (panel["cons_rank"] <= 4)
                                & (panel["is_branch"] == 0), "bvdid"])
in_sample = set(panel["bvdid"])
panel["sub_of_insample"] = (panel["guo_bvdid"].notna() & (panel["guo_bvdid"] != panel["bvdid"])
                            & panel["guo_bvdid"].isin(eligible_parent)).astype(int)
# network aggregates (e.g. DSGV, Credit Mutuel, Farm Credit System) whose members are also in the sample
panel["combined"] = panel["name"].str.contains(r"\(COMBINED", case=False, na=False).astype(int)
# US government-sponsored enterprises: not banks in the risk-shifting sense, huge balance sheets
panel["gse"] = panel["name"].str.contains(
    r"FEDERAL NATIONAL MORTGAGE|FEDERAL HOME LOAN MORTGAGE|FEDERAL HOME LOAN BANK|FARM CREDIT|"
    r"FEDERAL AGRICULTURAL MORTGAGE|AGFIRST|AGRIBANK|\bCOBANK\b|STUDENT LOAN MARKETING",
    case=False, na=False).astype(int)
# siblings: banks sharing a GUO that is NOT in the sample (e.g. Credit Agricole SA & CACIB under
# SAS Rue La Boetie) -> keep only the largest member per GUO-year, flag the rest
sib = panel[(panel["chosen"] == 1) & panel["guo_bvdid"].notna() & (panel["guo_bvdid"] != panel["bvdid"])
            & ~panel["guo_bvdid"].isin(eligible_parent) & ~panel["guo_bvdid"].str.contains(r"\*", na=False)
            & (panel["is_branch"] == 0)]
largest = sib.sort_values("ta", ascending=False).drop_duplicates(["guo_bvdid", "year"])
panel["sibling_dup"] = (panel.index.isin(sib.index) & ~panel.index.isin(largest.index)).astype(int)

# ---------- derived variables ----------
panel["region"] = np.where(panel["iso2"].isin(NORTH_AMERICA), "North America", "Europe")
panel["leverage"] = np.where(panel["te"] > 0, panel["ta"] / panel["te"], np.nan)
panel["equity_ratio"] = panel["te"] / panel["ta"]
panel["bs_gap"] = (panel["ta"] - panel["tl"] - panel["te"]) / panel["ta"]
panel["flag_bs_gap"] = (panel["bs_gap"].abs() > 0.02).astype(int)
panel["wsf_share"] = panel["st_wsf"] / panel["tl"]                 # wholesale funding / liabilities
panel["nondep_share"] = (panel["tl"] - panel["cust_dep"]) / panel["tl"]  # paper's definition
panel["loans_ta"] = panel["gross_loans"] / panel["ta"]
panel["llp_loans"] = panel["llp"] / panel["gross_loans"]
ratio_cols = ["equity_ratio", "bs_gap", "wsf_share", "nondep_share", "loans_ta", "llp_loans"]
panel[ratio_cols] = panel[ratio_cols].replace([np.inf, -np.inf], np.nan)
panel["main_special"] =panel["special"].isin(MAIN_SPECIAL).astype(int)

base = ((panel["chosen"] == 1) & (panel["cons_rank"] <= 4) & (panel["main_special"] == 1)
        & (panel["sub_of_insample"] == 0) & (panel["combined"] == 0) & (panel["sibling_dup"] == 0)
        & (panel["gse"] == 0) & (panel["is_branch"] == 0))

# parent/sub pairs that GUO misses (GUO blank). Within country-year, flag the smaller entity if
#  R1 near-duplicate: same first word in name and assets within 5% (e.g. Discover Financial / Discover Bank)
#  R2 group prefix : larger is a BHC with no GUO and smaller's name starts with the larger's core name
#                    (e.g. CREDIT AGRICOLE -> CREDIT AGRICOLE SA, BPCE GROUP -> BPCE SA)
GROUP_WORDS = r"\b(GROUP|GROUPE|GRUPPO|GRUPO|HOLDINGS?|CORPORATION|CORP|INC|PLC|SA|AG|NV)\b\.?"
cand = panel[base].copy()
GENERIC = set("""BANK BANCO BANCA BANQUE BANKA BANCORP BANCORPORATION BANCSHARES SAVINGS TRUST COMPANY CO
FINANCIAL FINANCE SERVICES NATIONAL ASSOCIATION NA N A FSB SSB FEDERAL STATE FIRST THE OF DE DU DES D L LA LE LES
DI DEL DELLA DER DIE UND AND & CAISSE REGIONALE CREDIT AGRICOLE MUTUEL COOPERATIVE COOPERATIVA SPARKASSE
VOLKSBANK RAIFFEISENBANK RAIFFEISEN EG SC SPA S P A AB ASA AS A S LTD LIMITED LLC INC CORP CORPORATION
GROUP GROUPE GRUPPO GRUPO HOLDING HOLDINGS SA AG NV PLC SE CREDITO COOPERATIVO SOCIETA CASSA RURALE ED
ARTIGIANA CAJA SOCIEDAD CAIXA MUTUO CRL C R DO DA ET E Y DBA UNION GENOSSENSCHAFT EGEN MBH KREISSPARKASSE
STADTSPARKASSE REGION SPAREBANK SPAREBANKEN 1""".split())


def distinct_tokens(name):
    toks = re.sub(r"[^A-Z0-9 ]", " ", str(name).upper()).split()
    return tuple(t for t in toks if t not in GENERIC)[:2]


cand["w1"] = cand["name"].map(distinct_tokens)
cand["core"] = (cand["name"].str.upper().str.replace(GROUP_WORDS, "", regex=True)
                .str.replace(r"[^A-Z0-9 ]", " ", regex=True).str.split().str.join(" "))
pair_dup = set()
for (_, _), g in cand.groupby(["iso2", "year"]):
    if len(g) < 2:
        continue
    g = g.sort_values("ta", ascending=False)
    rows = list(g[["ta", "w1", "core", "guo_bvdid", "special"]].itertuples())
    for i, big in enumerate(rows):
        for small in rows[i + 1:]:
            ratio = small.ta / big.ta
            if ratio < 0.3:
                break
            r1 = ratio >= 0.95 and len(small.w1) > 0 and small.w1 == big.w1
            r2 = (pd.isna(big.guo_bvdid) and big.special == "Bank holding company" and len(big.core) >= 4
                  and small.core.startswith(big.core) and small.Index != big.Index)
            if r1 or r2:
                pair_dup.add(small.Index)
panel["pair_dup"] = panel.index.isin(pair_dup).astype(int)
# French mutualist network members that are ALSO consolidated in an in-sample group statement
# (Credit Agricole group, BPCE group). Kept in main sample (separate legal banks), but drop them
# for asset-weighted aggregates to avoid double counting.
panel["network_member"] = ((panel["iso2"] == "FR") & panel["name"].str.contains(
    r"CREDIT AGRICOLE MUTUEL|CAISSE D.EPARGNE|BANQUE POPULAIRE|CREDIT MUTUEL", case=False, na=False)
    & (panel["combined"] == 0)).astype(int)

panel["keep_main"] = (base & (panel["pair_dup"] == 0) & panel["leverage"].notna()
                      & (panel["flag_bs_gap"] == 0)).astype(int)
# Europe has no data before 2005 in this subscription; North America from 1997

order = ["bvdid", "name", "iso2", "region", "year", "closing_date", "fye_month", "conscode", "acc_practice",
         "special", "main_special", "status", "status_date", "inactive", "listed", "sifi", "guo_bvdid",
         "ta", "te", "tl", "leverage", "equity_ratio", "cust_dep", "dep_stf", "st_wsf", "wsf_share",
         "nondep_share", "gross_loans", "loans_ta", "npl_ratio", "llr", "llp", "llp_loans", "ni", "roaa",
         "tier1", "car", "rwa_ta", "liq_ta", "liq_dstf", "bs_gap", "flag_bs_gap", "chosen", "sub_of_insample", "combined", "gse", "sibling_dup", "pair_dup", "network_member", "is_branch",
         "keep_main", "nace", "last_year", "part", "sid"]
panel = panel[order].sort_values(["bvdid", "year", "conscode"]).reset_index(drop=True)

main = panel[panel["keep_main"] == 1].copy()
assert not main.duplicated(["bvdid", "year"]).any()

cov = (main.groupby(["year", "region"]).size().unstack(fill_value=0)
       .join(main.groupby("year")["ta"].sum().div(1e9).rename("total_assets_tn_usd")))

panel.to_csv(f"{OUT}/bankfocus_panel_all.csv", index=False)
main.to_csv(f"{OUT}/bankfocus_panel_main.csv", index=False)
cov.to_csv(f"{OUT}/coverage_by_year.csv")


def to_dta(d, path):
    d = d.copy()
    for c in d.columns:
        if d[c].dtype == object:
            d[c] = d[c].fillna("").astype(str)
    d.to_stata(path, write_index=False, version=118,
               variable_labels={k: v[:80] for k, v in {**{v: k for k, v in VARMAP.items()},
                                                        **{v: k for k, v in IDMAP.items()}}.items() if k in d})


to_dta(panel, f"{OUT}/bankfocus_panel_all.dta")
to_dta(main, f"{OUT}/bankfocus_panel_main.dta")
print(f"all: {len(panel)} rows | main: {len(main)} bank-years, {main['bvdid'].nunique()} banks")
print(cov.to_string())

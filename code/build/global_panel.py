"""
Global BankFocus panel: merge 'global_core' and 'global_core_fx' list exports and clean.

Usage: python global_panel.py <core_dir> <fx_dir> <out_dir>

Both exports come from the same search (5,962 statements, TA >= USD 10bn in any year 1997-2026,
active + inactive, 11 bank specialisations, worldwide) with the same sort order, so rows are
aligned by their global position (part offset + rank) and checked on BvD ID + consolidation code.

Cleaning (same rules as build_panel.py for the NA+EU panel):
  one statement per BvD ID x year: C1 > C2 > U1 > C* (U2, U* dropped), ties -> IFRS > US GAAP >
  Local GAAP > most non-missing; drop subsidiaries of in-sample parents, network aggregates
  ("COMBINED"), GSEs, siblings under an out-of-sample GUO (keep largest), parent/sub pairs GUO
  misses; leverage = TA/TE (TE > 0); flag |A-L-E|/A > 2%; RWA/TA, Tier 1, CAR == 0 -> missing.
"""
import sys, glob, re
import numpy as np
import pandas as pd
from python_calamine import CalamineWorkbook

CORE, FX, OUT = (sys.argv[1:4] + [".", ".", "."])[:3] if len(sys.argv) > 1 else (".", ".", ".")

CODEMAP = {
    # core
    "52600": "ta", "63300": "te", "61900": "tl", "91300": "cust_dep", "91200": "dep_stf",
    "99605": "st_wsf", "PL": "ni", "99500": "roaa", "90100": "gross_loans", "99280": "npl_ratio",
    "51400": "llr", "72200": "llp", "99040": "tier1", "99050": "car", "99160": "rwa_ta",
    "99630": "liq_ta", "99680": "liq_dstf",
    "87160": "struct_fx_risk", "80590": "fx_income", "74800": "fx_transl_diff", "62700": "fx_reval_res",
    "CLOSING_DATE": "closing_date", "ACCOUNTING_PRACTICE": "acc_practice",
    "ORIGINAL_CURRENCY": "orig_ccy", "EXCHANGE_RATE": "fx_rate_usd",
    # FX derivatives
    "81900": "fxder_assets", "82080": "fxder_liab", "82260": "fxder_notional",
    # loans by currency
    "W18194": "loan_usd", "W18195": "loan_eur", "W18196": "loan_jpy", "W18197": "loan_gbp",
    "W18198": "loan_chf", "W18199": "loan_cad", "W18200": "loan_cny", "W18201": "loan_aud",
    "W18202": "loan_oth_fx", "W18203": "loan_fx_tot", "W18204": "loan_dom_ccy",
    # deposits by currency
    "W18206": "dep_usd", "W18207": "dep_eur", "W18208": "dep_jpy", "W18209": "dep_gbp",
    "W18210": "dep_chf", "W18211": "dep_cad", "W18212": "dep_cny", "W18213": "dep_aud",
    "W18214": "dep_oth_fx", "W18215": "dep_fx_tot", "W18216": "dep_dom_ccy",
    # loans / exposure by geography and market
    "W19393": "geo_loan_breakdown_type",
    "W19318": "geo_loan_americas", "W19319": "geo_loan_namerica", "W19320": "geo_loan_latam",
    "W19321": "geo_loan_europe", "W19322": "geo_loan_asia", "W19323": "geo_loan_africa",
    "W19324": "geo_loan_mideast", "W19325": "geo_loan_oceania", "W19326": "geo_loan_row",
    "W19327": "geo_loan_others", "W19328": "geo_loan_total",
    "W19329": "mkt_loan_domestic", "W19330": "mkt_loan_foreign", "W19331": "mkt_loan_total",
    # deposits / financial liabilities by geography and market
    "W19394": "geo_dep_breakdown_type",
    "W19332": "geo_dep_americas", "W19333": "geo_dep_namerica", "W19334": "geo_dep_latam",
    "W19335": "geo_dep_europe", "W19336": "geo_dep_asia", "W19337": "geo_dep_africa",
    "W19338": "geo_dep_mideast", "W19339": "geo_dep_oceania", "W19340": "geo_dep_row",
    "W19341": "geo_dep_others", "W19342": "geo_dep_total",
    "W19343": "mkt_dep_domestic", "W19344": "mkt_dep_foreign", "W19345": "mkt_dep_total",
}
TEXTVARS = {"closing_date", "acc_practice", "orig_ccy", "geo_loan_breakdown_type", "geo_dep_breakdown_type"}
IDMAP = {
    "NAME": "name", "BVD_ID_NUMBER": "bvdid", "COUNTRY_ISO_CODE": "iso2", "CONSOLIDATION_CODE": "conscode",
    "SPECIALISATION": "special", "STATUS": "status", "STATUS_DATE": "status_date",
    "GUO_BVD_ID_NUMBER": "guo_bvdid", "GUO_COUNTRY_ISO_CODE": "guo_iso2", "YEAR_LAST_ACCOUNTS": "last_year",
}
FLAGCOLS = {"Inactive": "inactive", "Quoted": "listed", "Sifi": "sifi", "Branch": "branch"}

MAIN_SPECIAL = {"Commercial bank", "Savings bank", "Cooperative bank", "Bank holding company",
                "Real estate & mortgage finance institution", "Investment bank"}
CONS_PRIORITY = {"C1": 1, "C2": 2, "U1": 3, "C*": 4, "U2": 5, "U*": 6}
ACC_PRIORITY = {"IFRS": 1, "US GAAP": 2, "Local GAAP": 3}

R = {
    "North America": "US CA",
    "Europe": "AT BE BG CH CY CZ DE DK EE ES FI FR GB GR HR HU IE IS IT LI LT LU LV MC MT NL NO PL PT RO "
              "SE SI SK SM AD GG JE IM GI FO",
    "Emerging Europe & CIS": "RU UA BY KZ TR RS BA ME MK AL MD GE AM AZ UZ KG TJ TM XK",
    "Japan & Developed Asia-Pacific": "JP AU NZ SG HK KR TW",
    "China": "CN MO",
    "Emerging Asia": "IN ID MY TH PH VN PK BD LK KH MM LA MN NP BN",
    "Latin America": "BR MX AR CL CO PE UY PY BO EC VE PA CR GT HN SV NI DO JM TT BS BB KY BM VG CW PR",
    "Middle East & Africa": "AE SA QA KW BH OM IL JO LB EG MA TN DZ LY NG ZA KE GH ET TZ UG AO MU NA BW "
                            "ZM ZW CI SN CM IQ IR SD",
}
REGION = {c: k for k, v in R.items() for c in v.split()}


def read_dir(d):
    files = sorted(glob.glob(f"{d}/*.xlsx"), key=lambda f: int(re.search(r"part(\d+)", f).group(1)))
    out, offset = [], 0
    for f in files:
        rows = CalamineWorkbook.from_path(f).get_sheet_by_name("Results").to_python()
        h1, h2 = rows[0], rows[1]
        cols = []
        for a, b in zip(h1, h2):
            m = re.match(r"(?s)(.*?)\n?(?:th USD |USD )?(\d{4}|Last avail\. yr)$", str(a))
            if m and b:
                cols.append(f"{b}@{m.group(2)}")
            elif b:
                cols.append(b)
            else:
                cols.append(str(a).strip() or "rank")
        df = pd.DataFrame(rows[2:], columns=cols)
        df = df[df["BVD_ID_NUMBER"].astype(str).str.strip() != ""].copy()
        df["gpos"] = offset + df["rank"].astype(str).str.rstrip(".").astype(int)
        offset += len(df)
        out.append(df)
    return pd.concat(out, ignore_index=True), len(files)


core, nc = read_dir(CORE)
fx, nf = read_dir(FX)
key = ["gpos", "BVD_ID_NUMBER", "CONSOLIDATION_CODE"]
chk = core[key].merge(fx[key], on="gpos", suffixes=("", "_fx"))
mismatch = ((chk["BVD_ID_NUMBER"] != chk["BVD_ID_NUMBER_fx"]) |
            (chk["CONSOLIDATION_CODE"] != chk["CONSOLIDATION_CODE_fx"])).sum()
print(f"core {nc} files / {len(core)} rows, fx {nf} files / {len(fx)} rows, aligned {len(chk)}, mismatches {mismatch}")
assert mismatch == 0 and len(chk) == len(core) == len(fx)
fx_keep = ["gpos"] + [c for c in fx.columns if "@" in c and c.split("@")[0] not in
                      ("CLOSING_DATE", "ACCOUNTING_PRACTICE", "ORIGINAL_CURRENCY", "EXCHANGE_RATE")]
wide = core.merge(fx[fx_keep], on="gpos", suffixes=("", "_dup"))
wide = wide[[c for c in wide.columns if not c.endswith("_dup")]]

# ---------- wide -> long ----------
pieces = []
for c in wide.columns:
    if "@" not in c:
        continue
    code, yr = c.split("@")
    if yr.startswith("Last") or code not in CODEMAP or int(yr) > 2025:
        continue
    var = CODEMAP[code]
    s = wide[c].replace({"n.a.": np.nan, "": np.nan})
    if var not in TEXTVARS:
        s = pd.to_numeric(s, errors="coerce")
    pieces.append(pd.DataFrame({"gpos": wide["gpos"], "year": int(yr), "var": var, "val": s}))
long = pd.concat(pieces).dropna(subset=["val"])
istext = long["var"].isin(TEXTVARS)
num = long[~istext].pivot_table(index=["gpos", "year"], columns="var", values="val", aggfunc="first").astype(float)
txt = long[istext].pivot_table(index=["gpos", "year"], columns="var", values="val", aggfunc="first")
panel = num.join(txt, how="left").reset_index()
panel = panel[panel["ta"] > 0]

ids = wide[["gpos"] + list(IDMAP) + list(FLAGCOLS)].rename(columns={**IDMAP, **FLAGCOLS})
ids["status_date"] = pd.to_datetime(ids["status_date"].replace("", np.nan), errors="coerce")
ids.loc[ids["status_date"].dt.year < 1950, "status_date"] = pd.NaT
for c in ["guo_bvdid", "guo_iso2"]:
    ids[c] = ids[c].replace("", np.nan)
panel = panel.merge(ids, on="gpos", how="left")
panel["closing_date"] = pd.to_datetime(panel["closing_date"], errors="coerce")
panel["fye_month"] = panel["closing_date"].dt.month
for v in ["rwa_ta", "tier1", "car"]:
    panel.loc[panel[v] == 0, v] = np.nan

# ---------- one statement per bank-year ----------
valvars = [v for v in CODEMAP.values() if v not in TEXTVARS and v in panel]
panel["n_nonmiss"] = panel[valvars].notna().sum(axis=1)
panel["cons_rank"] = panel["conscode"].map(CONS_PRIORITY).fillna(9)
panel["acc_rank"] = panel["acc_practice"].map(ACC_PRIORITY).fillna(9)
panel = panel.sort_values(["bvdid", "year", "cons_rank", "acc_rank", "n_nonmiss"],
                          ascending=[True, True, True, True, False]).reset_index(drop=True)
panel["chosen"] = (~panel.duplicated(["bvdid", "year"])).astype(int)

# ---------- group double counting ----------
panel["main_special"] = panel["special"].isin(MAIN_SPECIAL).astype(int)
panel["is_branch"] = (panel["branch"] == "Yes").astype(int)
# parent counts only if it is itself an eligible bank statement (e.g. KB Financial Group is a
# "Finance company", so Kookmin Bank must stay)
eligible_parent = set(panel.loc[(panel["main_special"] == 1) & (panel["cons_rank"] <= 4)
                                & (panel["is_branch"] == 0), "bvdid"])
in_sample = set(panel["bvdid"])
panel["sub_of_insample"] = (panel["guo_bvdid"].notna() & (panel["guo_bvdid"] != panel["bvdid"])
                            & panel["guo_bvdid"].isin(eligible_parent)).astype(int)
panel["combined"] = panel["name"].str.contains(r"\(COMBINED", case=False, na=False).astype(int)
panel["gse"] = panel["name"].str.contains(
    r"FEDERAL NATIONAL MORTGAGE|FEDERAL HOME LOAN MORTGAGE|FEDERAL HOME LOAN BANK|FARM CREDIT|"
    r"FEDERAL AGRICULTURAL MORTGAGE|AGFIRST|AGRIBANK|\bCOBANK\b|STUDENT LOAN MARKETING",
    case=False, na=False).astype(int)
# GUO ids containing '*' are entities outside the BvD database, typically states / public
# authorities (e.g. Central Huijin owns ICBC, CCB, ABC, BOC): those are not one banking group
sib = panel[(panel["chosen"] == 1) & panel["guo_bvdid"].notna() & (panel["guo_bvdid"] != panel["bvdid"])
            & ~panel["guo_bvdid"].isin(eligible_parent) & ~panel["guo_bvdid"].str.contains(r"\*", na=False)
            & (panel["is_branch"] == 0)]
largest = sib.sort_values("ta", ascending=False).drop_duplicates(["guo_bvdid", "year"])
panel["sibling_dup"] = (panel.index.isin(sib.index) & ~panel.index.isin(largest.index)).astype(int)
base = ((panel["chosen"] == 1) & (panel["cons_rank"] <= 4) & (panel["main_special"] == 1)
        & (panel["sub_of_insample"] == 0) & (panel["combined"] == 0) & (panel["sibling_dup"] == 0)
        & (panel["gse"] == 0) & (panel["is_branch"] == 0))

GENERIC = set("""BANK BANCO BANCA BANQUE BANKA BANCORP BANCORPORATION BANCSHARES SAVINGS TRUST COMPANY CO
FINANCIAL FINANCE SERVICES NATIONAL ASSOCIATION NA N A FSB SSB FEDERAL STATE FIRST THE OF DE DU DES D L LA LE LES
DI DEL DELLA DER DIE UND AND & CAISSE REGIONALE CREDIT AGRICOLE MUTUEL COOPERATIVE COOPERATIVA SPARKASSE
VOLKSBANK RAIFFEISENBANK RAIFFEISEN EG SC SPA S P A AB ASA AS A S LTD LIMITED LLC INC CORP CORPORATION
GROUP GROUPE GRUPPO GRUPO HOLDING HOLDINGS SA AG NV PLC SE CREDITO COOPERATIVO SOCIETA CASSA RURALE ED
ARTIGIANA CAJA SOCIEDAD CAIXA MUTUO CRL C R DO DA ET E Y DBA UNION GENOSSENSCHAFT EGEN MBH KREISSPARKASSE
STADTSPARKASSE REGION SPAREBANK SPAREBANKEN 1 PT TBK PUBLIC JOINT STOCK PJSC JSC OJSC CJSC BHD BERHAD
COMMERCIAL DEVELOPMENT INTERNATIONAL""".split())
GROUP_WORDS = r"\b(GROUP|GROUPE|GRUPPO|GRUPO|HOLDINGS?|CORPORATION|CORP|INC|PLC|SA|AG|NV)\b\.?"


def distinct_tokens(name):
    toks = re.sub(r"[^A-Z0-9 ]", " ", str(name).upper()).split()
    return tuple(t for t in toks if t not in GENERIC)[:2]


cand = panel[base].copy()
cand["w1"] = cand["name"].map(distinct_tokens)
cand["core"] = (cand["name"].str.upper().str.replace(GROUP_WORDS, "", regex=True)
                .str.replace(r"[^A-Z0-9 ]", " ", regex=True).str.split().str.join(" "))
pair_dup = set()
for _, g in cand.groupby(["iso2", "year"]):
    if len(g) < 2:
        continue
    rows = list(g.sort_values("ta", ascending=False)[["ta", "w1", "core", "guo_bvdid", "special"]].itertuples())
    for i, big in enumerate(rows):
        for small in rows[i + 1:]:
            ratio = small.ta / big.ta
            if ratio < 0.3:
                break
            r1 = ratio >= 0.95 and len(small.w1) > 0 and small.w1 == big.w1
            r2 = (pd.isna(big.guo_bvdid) and big.special == "Bank holding company" and len(big.core) >= 4
                  and small.core.startswith(big.core))
            if r1 or r2:
                pair_dup.add(small.Index)
panel["pair_dup"] = panel.index.isin(pair_dup).astype(int)
panel["network_member"] = ((panel["iso2"] == "FR") & panel["name"].str.contains(
    r"CREDIT AGRICOLE MUTUEL|CAISSE D.EPARGNE|BANQUE POPULAIRE|CREDIT MUTUEL", case=False, na=False)
    & (panel["combined"] == 0)).astype(int)

# ---------- derived ----------
panel["region"] = panel["iso2"].map(REGION).fillna("Other")
panel["leverage"] = np.where(panel["te"] > 0, panel["ta"] / panel["te"], np.nan)
panel["equity_ratio"] = panel["te"] / panel["ta"]
panel["bs_gap"] = (panel["ta"] - panel["tl"] - panel["te"]) / panel["ta"]
panel["flag_bs_gap"] = (panel["bs_gap"].abs() > 0.02).astype(int)
panel["wsf_share"] = panel["st_wsf"] / panel["tl"]
panel["nondep_share"] = (panel["tl"] - panel["cust_dep"]) / panel["tl"]
panel["loans_ta"] = panel["gross_loans"] / panel["ta"]
panel["llp_loans"] = panel["llp"] / panel["gross_loans"]
# FX exposure measures
loans_ccy = panel["loan_fx_tot"] + panel["loan_dom_ccy"]
deps_ccy = panel["dep_fx_tot"] + panel["dep_dom_ccy"]
panel["fx_loan_share"] = panel["loan_fx_tot"] / loans_ccy
panel["usd_loan_share"] = panel["loan_usd"] / loans_ccy
panel["fx_dep_share"] = panel["dep_fx_tot"] / deps_ccy
panel["usd_dep_share"] = panel["dep_usd"] / deps_ccy
# require both components (foreign == total with domestic missing is ambiguous)
panel["foreign_mkt_loan_share"] = panel["mkt_loan_foreign"] / (panel["mkt_loan_foreign"] + panel["mkt_loan_domestic"])
panel["foreign_mkt_dep_share"] = panel["mkt_dep_foreign"] / (panel["mkt_dep_foreign"] + panel["mkt_dep_domestic"])
panel["fxder_notional_ta"] = panel["fxder_notional"] / panel["ta"]
panel["fxder_assets_ta"] = panel["fxder_assets"] / panel["ta"]
panel["foreign_owned"] = np.where(panel["guo_iso2"].isna(), np.nan,
                                  (panel["guo_iso2"] != panel["iso2"]).astype(float))
ratio_cols = ["equity_ratio", "bs_gap", "wsf_share", "nondep_share", "loans_ta", "llp_loans", "fx_loan_share",
              "usd_loan_share", "fx_dep_share", "usd_dep_share", "foreign_mkt_loan_share",
              "foreign_mkt_dep_share", "fxder_notional_ta", "fxder_assets_ta"]
panel[ratio_cols] = panel[ratio_cols].replace([np.inf, -np.inf], np.nan)
for c in ["fx_loan_share", "usd_loan_share", "fx_dep_share", "usd_dep_share",
          "foreign_mkt_loan_share", "foreign_mkt_dep_share"]:
    panel.loc[~panel[c].between(0, 1), c] = np.nan   # inconsistent sub-totals

# unit / currency-conversion errors in BvD (e.g. Libya NCB 2007-08 ~1,000x, Turkmenistan 2005-06 ~5,000x,
# Ghana 2006, Zimbabwe 2018). Split each bank's series at year-to-year jumps of >= 200x in total assets and flag
# every segment except the longest one. Genuine restructurings (Hypo Real Estate 2015: ~60x) are not affected.
panel["flag_unit_error"] = 0
_ch = panel[panel["chosen"] == 1].sort_values(["bvdid", "year"])
_jump = np.log(_ch["ta"]).groupby(_ch["bvdid"]).diff().abs() > np.log(200)
_seg = _jump.astype(int).groupby(_ch["bvdid"]).cumsum()
_len = _seg.groupby([_ch["bvdid"], _seg]).transform("size")
_maxlen = _len.groupby(_ch["bvdid"]).transform("max")
_main_seg = _seg.where(_len == _maxlen).groupby(_ch["bvdid"]).transform("min")
# genuine collapses into shells happen in advanced markets (Washington Mutual -> "Mr. Cooper Group", Hypo Real
# Estate), so the rule is applied only to banks outside North America, Europe and Japan & Developed Asia-Pacific
_em = ~panel.loc[_ch.index, "region"].isin(["North America", "Europe", "Japan & Developed Asia-Pacific"]).values
panel.loc[_ch.index[(_seg != _main_seg).values & _em], "flag_unit_error"] = 1
panel["keep_main"] = (base & (panel["pair_dup"] == 0) & (panel["flag_unit_error"] == 0) & panel["leverage"].notna()
                      & (panel["flag_bs_gap"] == 0)).astype(int)

front = ["bvdid", "name", "iso2", "region", "year", "closing_date", "fye_month", "conscode", "acc_practice",
         "orig_ccy", "fx_rate_usd", "special", "status", "status_date", "inactive", "listed", "sifi",
         "guo_bvdid", "guo_iso2", "foreign_owned", "branch", "ta", "te", "tl", "leverage", "equity_ratio",
         "cust_dep", "dep_stf", "st_wsf", "wsf_share", "nondep_share", "gross_loans", "loans_ta",
         "npl_ratio", "llr", "llp", "llp_loans", "ni", "roaa", "tier1", "car", "rwa_ta", "liq_ta", "liq_dstf",
         "fx_loan_share", "usd_loan_share", "fx_dep_share", "usd_dep_share", "foreign_mkt_loan_share",
         "foreign_mkt_dep_share", "fxder_notional_ta", "fxder_assets_ta",
         "fxder_assets", "fxder_liab", "fxder_notional", "struct_fx_risk", "fx_income", "fx_transl_diff",
         "fx_reval_res"]
raw_w = [v for v in CODEMAP.values() if v.startswith(("loan_", "dep_", "geo_", "mkt_")) and v in panel
         and v not in front]
flags = ["bs_gap", "flag_bs_gap", "chosen", "sub_of_insample", "combined", "gse", "sibling_dup", "pair_dup",
         "network_member", "is_branch", "flag_unit_error", "main_special", "keep_main", "last_year", "gpos"]
panel = panel[[c for c in front + raw_w + flags if c in panel]].sort_values(["bvdid", "year", "conscode"])
main = panel[panel["keep_main"] == 1].copy()
assert not main.duplicated(["bvdid", "year"]).any()

panel.to_csv(f"{OUT}/global_panel_all.csv", index=False)
main.to_csv(f"{OUT}/global_panel_main.csv", index=False)


def to_dta(d, path):
    d = d.copy()
    for c in d.columns:
        if d[c].dtype == object or str(d[c].dtype).startswith("str"):
            d[c] = d[c].fillna("").astype(str)
    d.to_stata(path, write_index=False, version=118)


to_dta(main, f"{OUT}/global_panel_main.dta")
to_dta(panel, f"{OUT}/global_panel_all.dta")

cov = main.groupby(["year", "region"]).size().unstack(fill_value=0)
cov.to_csv(f"{OUT}/global_coverage_by_year_region.csv")
print(f"all: {len(panel)} rows | main: {len(main)} bank-years, {main['bvdid'].nunique()} banks")
print(cov.to_string())

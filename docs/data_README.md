# BankFocus 글로벌 은행 패널 (Coimbra & Rey 재현 + FX 확장)

Moody's **BankFocus**(옛 Bankscope) 재무제표로 만든 **글로벌 은행-연도 패널**입니다. Coimbra & Rey (2024, *Review of Economic Studies*), "Financial Cycles with Heterogeneous Intermediaries"의 레버리지 stylized facts를 재현하고, 외화 노출(FX)로 확장하기 위해 만들었어요. **모든 결과는 이 글로벌 패널 하나로만 계산했습니다.** 미국 결과도 이 패널 안의 미국 은행으로 냈어요.

- 작성: 2026-10-22
- BankFocus 데이터 업데이트: 16/10/2026 (update no. 399155)
- 원자료 export: 2026-10-22

> **⚠️ 라이선스**
> BankFocus는 Moody's(BvD)의 유료 라이선스 데이터입니다. 이 파일들은 **같은 라이선스를 가진 기관 사용자 사이에서만** 공유하세요. 은행 단위 데이터를 외부에 재배포하거나 공개 저장소에 올리면 안 됩니다. 논문에는 집계 통계, 회귀 결과, 그림만 싣는 걸 원칙으로 합니다.

---

## 1. 한눈에 보기

| 항목 | 내용 |
|---|---|
| 표본 기준 | 전 세계 은행 중 1997–2026년에 **한 해라도 자산 100억 달러 이상** |
| 메인 표본 (`keep_main==1`) | **은행 1,853개, 은행-연도 27,823개** |
| 기간 | 1997–2025. **북미만 1997년부터**, 나머지 지역은 2004–05년부터 |
| 지역별 은행 수 | 유럽 546, 북미 486, 일본·선진아시아 256, 중국 207, 신흥아시아 114, 중동·아프리카 102, 중남미 93, 신흥유럽·CIS 42 |
| 미국 은행 | 연 161–265개 (메인 표본 기준) |
| FX·통화별·지역별 변수 | ✅ 포함 |

**처음 쓰는 분은 `data/global_panel_main.dta`(또는 `.csv`) 하나만 열면 됩니다.**

---

## 2. 파일 구성 (데이터는 저장소 밖 `DATA_ROOT`에 있음)

```
DATA_ROOT  (예: C:\Users\USER\Desktop\HG\Archive\Data\Bankfocus)   ← Git에 올리지 않음
├── README_data.md                     export별 검색 조건·템플릿·날짜
├── raw\2026-10-22_global\core\        BankFocus core export 5개 (xlsx)
├── raw\2026-10-22_global\fx\          BankFocus FX export 11개 (xlsx)
└── derived\global_panel\v2026-10-24\
    ├── global_panel_main.dta / .csv   ★ 핵심: 메인 표본 (은행-연도당 1행)
    ├── global_panel_all.csv           모든 재무제표-연도 + 클리닝 플래그 (robustness용)
    ├── global_coverage_by_year_region.csv
    └── MANIFEST.txt                   생성 시각, 사용한 Git 커밋, 파일 해시

bankfocus-coimbra-rey  (이 저장소)
├── run.py                             파이프라인 실행 (build / analysis)
├── config\paths.example.ini           데이터 경로 예시 → paths.local.ini로 복사
├── code\build\global_panel.py          패널 생성 (core + FX export 병합·클리닝)
├── code\analysis\cr_analysis.py        그림 + 회귀 (논문 eq. 1, FX 확장)
├── code\analysis\region_gfc.py         권역·국가별 Figure 1과 GFC 이질성, 집중도 (7.5절)
├── code\legacy\                        초기 북미+유럽(v3) 코드 (참고용)
├── data_public\us_ffr_annual.csv       미국 명목/실질 Fed Funds rate (연평균, FRED)
└── output\
    ├── figures\                        PNG 그림 (figG*: 7절, figR*: 7.5절)
    ├── tables\                         ★ cr_tables.tex, region_gfc_tables.tex (article), table_*.tex (\input 용)
    ├── region\                         권역·국가별 집계 CSV (7.5절)
    └── analysis_summary.txt           그림·회귀 수치 요약
```

- **`_main`**: 분석용. 은행(BvD ID)-연도당 정확히 1행이고, 4절의 클리닝 규칙을 모두 적용했습니다.
- **`_all`**: 같은 은행의 연결·개별 재무제표와 제외된 기관까지 모두 포함하고, 제외 사유를 플래그로 남겼어요. 규칙을 바꿔 robustness를 돌릴 때 씁니다.
- `.dta`는 Stata 14 이상(version 118), `.csv`는 UTF-8입니다.

---

## 3. 표본 구성 (BankFocus 검색 조건)

| 단계 | 조건 |
|---|---|
| 1 | Status: Active + Inactive (파산·합병 은행 포함) |
| 2 | Total assets (TOAS) ≥ USD 10,000m, 1997–2026 중 **한 해라도** 해당 (연간 기준, "at least one of the selected periods") |
| 3 | Specialisation 11개: Commercial bank, Savings bank, Cooperative bank, Real estate & mortgage finance institution, Investment bank, Other non banking credit institution, Specialized governmental credit institution, Bank holding company, Securities firm, Private banking, Finance company |

→ **5,962개 재무제표 (BvD ID 3,260개)**. 지역 조건은 없습니다.

**설정**
- **Search options:** "Exclude companies with no recent financial data"와 "Start all searches with a search on active companies"를 **해제**했어요. 켜져 있으면 2021년 이전에 사라진 은행(Lehman, Wachovia 등)이 빠져서 생존 편향이 생깁니다.
- **단위:** thousand USD, 환율은 *at each closing date*(그해 결산일 환율)
- **Fiscal year end option:** 31/03

**Export 구성 (같은 검색, 같은 정렬로 두 번 받아 행 단위로 병합)**
- **core** (1,200개씩 5번): 식별 변수 + Closing date, Accounting practice, Original currency, Exchange rate + 5.2·5.3절 변수 + 87160, 80590, 74800, 62700
- **FX** (550개씩 11번): 식별 변수 + Closing date 등 + 81900, 82080, 82260 + W 코드 전부(5.5절)
- 두 export의 5,962행은 BvD ID와 consolidation code가 **모두 일치**합니다(불일치 0건).

---

## 4. 클리닝 규칙 (`_main` 파일에 적용됨)

| # | 규칙 | `_all`의 플래그 |
|---|---|---|
| 1 | `n.a.` → 결측, 2026년 제외, 자산 ≤ 0 제외 | |
| 2 | RWA/TA, Tier 1, CAR이 정확히 0이면 결측 (BvD가 결측을 0으로 채우는 경우) | |
| 3 | **은행-연도당 재무제표 1개 선택.** Consolidation code 우선순위 C1 > C2 > U1 > C\*. U2, U\*는 제외(C2와 중복). 같은 코드가 여럿이면 IFRS > US GAAP > Local GAAP, 그다음 결측이 적은 것 | `chosen` |
| 4 | **표본 안에 모회사가 있는 자회사 제외.** 모회사(GUO)가 메인 표본 자격이 있을 때만 적용해요(예: KB금융지주는 "Finance company"라서 국민은행은 유지) | `sub_of_insample` |
| 5 | **네트워크 합산 재무제표 제외** (DSGV, Crédit Mutuel, Farm Credit System 등 이름에 "(COMBINED)") | `combined` |
| 6 | **미국 GSE 제외** (Fannie Mae, Federal Home Loan Banks, Farm Credit 계열, CoBank) | `gse` |
| 7 | **같은 GUO 아래 형제 계열사 중 가장 큰 곳만 유지** (GUO가 표본 밖일 때). 단 GUO ID에 `*`가 있는 **국가·정부 소유주**는 한 그룹으로 보지 않아요(예: Central Huijin이 소유한 ICBC, CCB, ABC, BOC는 모두 유지) | `sibling_dup` |
| 8 | **GUO로 안 잡히는 지주회사-자회사 쌍 제외.** 같은 나라·연도에서 고유명사가 같고 자산 차이가 5% 이내이거나, GUO 없는 지주회사 이름이 자회사 이름의 앞부분인 경우(예: Discover Financial / Discover Bank) | `pair_dup` |
| 9 | **지점(branch) 제외.** 본점 그룹 재무제표를 그대로 보고하는 경우가 있어요(예: Bank of China 싱가포르 지점) | `is_branch` |
| 10 | Specialisation이 메인 6개 유형일 때만 유지: Commercial, Savings, Cooperative, Bank holding company, Real estate & mortgage, Investment bank | `main_special` |
| 11 | 자본 ≤ 0이면 레버리지 결측, 해당 행 제외 | |
| 12 | 대차대조표 항등식 오차 \|A − L − E\| / A > 2%이면 제외 | `flag_bs_gap`, `bs_gap` |
| 13 | **BvD 단위·통화 환산 오류 제외.** 같은 은행 자산이 인접 연도 대비 200배 이상 점프하면 시계열을 끊고, 가장 긴 구간 외의 구간을 오류로 봐요. 신흥국 통화 환산 오류만 해당하도록 북미·유럽·일본·선진아시아 외 지역에만 적용합니다(리비아 NCB 2005–08, 투르크메니스탄 2005–06, 가나 2006, 짐바브웨 2018– 등 11개 은행 24건). 실제로 자산이 급감한 Washington Mutual 지주회사("Mr. Cooper Group"으로 이어짐)와 Hypo Real Estate는 영향받지 않아요 | `flag_unit_error` |

최종적으로 `keep_main == 1`인 행이 `_main` 파일입니다.

**표시만 하고 제외하지 않은 것**
- **`network_member == 1`:** 프랑스 협동조합 네트워크 회원사(Crédit Agricole 지역금고, Caisse d'Épargne, Banque Populaire, Crédit Mutuel). 개별 은행으로는 유효하지만 그룹 연결재무제표에도 포함돼 있으니 **자산 합계나 자산가중 지표를 낼 때는 빼세요.** 분석 코드는 이들을 뺍니다.
- 레버리지 **winsorize는 하지 않았어요.** 특수목적 법인 때문에 최댓값이 매우 큽니다. 분석 전에 연도별 1/99% winsorize를 권장해요(`cr_analysis.py`가 그렇게 합니다).

**검증:** 2024년 총자산 상위는 ICBC, ABC, CCB, BOC, JPMorgan, BofA, HSBC, BNP, MUFG 순이고, 지역별 총자산은 중국 50.4조, 유럽 44.8조, 북미 31.2조, 일본·선진아시아 27.3조 달러입니다.

---

## 5. 변수 설명

### 5.1 식별·분류 변수
| 변수 | 설명 |
|---|---|
| `bvdid` | BvD ID number. **패널 식별자**(은행) |
| `name` | 회사명 (Latin alphabet) |
| `iso2` | 국가 ISO 2자리 코드 |
| `region` | North America / Europe / Emerging Europe & CIS / Japan & Developed Asia-Pacific (JP, AU, NZ, SG, HK, KR, TW) / China (CN, MO) / Emerging Asia / Latin America / Middle East & Africa / Other |
| `year` | 회계연도 (BvD 기준) |
| `closing_date`, `fye_month` | 결산일, 결산월. **일본은 대부분 3월 결산** |
| `conscode` | 선택된 재무제표의 consolidation code (C1, C2, U1, C\*) |
| `acc_practice` | IFRS / US GAAP / Local GAAP |
| `orig_ccy`, `fx_rate_usd` | 보고 통화, 결산일 기준 USD 환율. **현지통화 금액 = USD 금액 / fx_rate_usd** |
| `special` | BankFocus specialisation |
| `status`, `status_date` | 현재 상태(Active, Dissolved (merger), Bankruptcy 등)와 상태 변경일 |
| `inactive`, `listed`, `sifi`, `branch` | Yes/No 플래그 (비활성, 상장, G-SIFI, 지점) |
| `guo_bvdid`, `guo_iso2` | 최종 모회사(Global Ultimate Owner, 50.01% 기준) ID와 국가 |
| `foreign_owned` | GUO 국가 ≠ 은행 국가이면 1. GUO는 **현재 시점 기준** |

### 5.2 핵심 재무 변수 (금액은 **thousand USD**, 결산일 환율)
| 변수 | BvD 코드 | 설명 |
|---|---|---|
| `ta` | 52600 | Total assets (Detailed format) |
| `te` | 63300 | Total equity |
| `tl` | 61900 | Total liabilities (Detailed format) |
| `cust_dep` | 91300 | Total customer deposits |
| `dep_stf` | 91200 | Deposits and short-term funding |
| `st_wsf` | 99605 | Short-term wholesale funding |
| `gross_loans` | 90100 | Gross loans & advances to customers |
| `llr` | 51400 | Loan loss reserves (잔액) |
| `llp` | 72200 | Net impairment charges on loans (당기 전입액) |
| `ni` | PL | Net income |

### 5.3 BvD 비율 변수 (단위: **%**)
| 변수 | BvD 코드 | 설명 |
|---|---|---|
| `roaa` | 99500 | ROAA |
| `npl_ratio` | 99280 | Impaired loans / Gross customer loans |
| `tier1` | 99040 | Tier 1 ratio (as reported). Basel I/II/III 정의 변화로 시계열 단절 있음 |
| `car` | 99050 | Total capital adequacy ratio (as reported) |
| `rwa_ta` | 99160 | RWA / Total assets (risk density) |
| `liq_ta` | 99630 | Liquid assets / Total assets |
| `liq_dstf` | 99680 | Liquid assets / Deposits & short-term funding |

### 5.4 직접 계산한 변수 (단위: **비율 0–1**)
| 변수 | 정의 |
|---|---|
| **`leverage`** | **ta / te** (te > 0일 때). 논문의 레버리지 정의 |
| `equity_ratio` | te / ta |
| `nondep_share` | (tl − cust_dep) / tl. 논문의 비예금(wholesale) 조달 비중 정의 |
| `wsf_share` | st_wsf / tl |
| `loans_ta` | gross_loans / ta |
| `llp_loans` | llp / gross_loans |
| `bs_gap` | (ta − tl − te) / ta |

### 5.5 FX 노출 변수
**직접 계산한 지표** (비율 0–1. 범위를 벗어나면 결측 처리. `fxder_*_ta`는 배수라 1을 넘을 수 있음)
| 변수 | 정의 | 메인 표본 커버리지 |
|---|---|---|
| **`fxder_notional_ta`** | FX 파생상품 명목금액 / 자산 | 은행 1,015개, 1997– (미국 위주) |
| `fxder_assets_ta` | FX 파생상품 자산 / 자산 | |
| **`foreign_mkt_loan_share`** | 해외시장 대출·익스포저 / (국내 + 해외). 국내·해외 값이 **둘 다 있을 때만** 계산 | 은행 627개, 2004– (유럽·일본·중국 위주) |
| `foreign_mkt_dep_share` | 해외시장 예금·금융부채 / (국내 + 해외) | 은행 295개 |
| **`fx_loan_share`** | 외화대출 / (외화대출 + 자국통화 대출) | 은행 408개, 2005– (중국·이탈리아·스위스·신흥국 위주) |
| `usd_loan_share` | USD 대출 / 전체 대출 | 은행 368개 |
| `fx_dep_share`, `usd_dep_share` | 예금 기준 같은 정의 | 은행 약 358개 |

**원자료 (thousand USD)**
| 변수 | BvD 코드 | 위치 (BankFocus Add/remove columns 트리) |
|---|---|---|
| `fxder_assets`, `fxder_liab`, `fxder_notional` | 81900, 82080, 82260 | Global Detailed Format → Notes: Derivatives |
| `struct_fx_risk` | 87160 | Total structural currency risk |
| `fx_income` | 80590 | Income from foreign exchange (ex trading) |
| `fx_transl_diff` | 74800 | Foreign currency translation differences (해외 자회사 신호) |
| `fx_reval_res` | 62700 | Foreign exchange revaluation reserves |
| `loan_usd`, `loan_eur`, `loan_jpy`, `loan_gbp`, `loan_chf`, `loan_cad`, `loan_cny`, `loan_aud`, `loan_oth_fx`, `loan_fx_tot`, `loan_dom_ccy` | W18194–W18204 | National format → **Moody's Analytics Bank** → Notes → Asset Quality Data → Loans And Deposits By Currency |
| `dep_usd` … `dep_aud`, `dep_oth_fx`, `dep_fx_tot`, `dep_dom_ccy` | W18206–W18216 | 같은 폴더 |
| `geo_loan_*` (americas, namerica, latam, europe, asia, africa, mideast, oceania, row, others, total) | W19318–W19328 | Asset Quality Data → Borrower / credit exposure… |
| `mkt_loan_domestic`, `mkt_loan_foreign`, `mkt_loan_total` | W19329–W19331 | 같은 폴더 |
| `geo_dep_*`, `mkt_dep_*` | W19332–W19345 | 같은 폴더 (예금·금융부채) |
| `geo_loan_breakdown_type`, `geo_dep_breakdown_type` | W19393, W19394 | 지역 구분 기준(텍스트). **지역별 변수를 쓰기 전에 꼭 확인** |

> W 코드 변수는 BankFocus 검색창에서 검색되지 않아요. 컬럼 트리에서 폴더를 직접 열어야 찾을 수 있습니다.

### 5.6 플래그·내부 변수
`chosen`, `sub_of_insample`, `combined`, `gse`, `sibling_dup`, `pair_dup`, `network_member`, `is_branch`, `flag_unit_error`, `main_special`, `flag_bs_gap`, `keep_main`은 4절 참고. `last_year`는 BvD의 마지막 재무제표 연도이고, `gpos`는 원자료 행 번호(검색 결과 순위)입니다.

### 5.7 거시 변수 (`us_ffr_annual.csv`)
| 변수 | 정의 |
|---|---|
| `ffr_nominal` | 연평균 effective Fed Funds rate (FRED: FEDFUNDS) |
| `cpi_infl` | 연평균 CPI 상승률 (FRED: CPIAUCSL. 2025년 10월은 FRED 결측이라 11개월 평균) |
| `ffr_real` | ffr_nominal − cpi_infl (사후 실질금리) |

---

## 6. 꼭 알아야 할 데이터 한계

1. **미국·캐나다 외 지역은 2004–05년부터입니다.** 이 구독의 BankFocus에는 유럽·아시아 은행의 2005년 이전 재무제표가 없어요(Deutsche Bank 등 확인). 그래서 **1997–2004년 결과는 사실상 미국 결과**입니다.
2. **커버리지가 크게 바뀌는 해가 있어요.** 미국은 2001년에 은행 수가 162개에서 249개로 늘고, 중국은 2011–13년에 66개에서 109개로 늘어납니다. 분위수나 자산가중 지표는 **표본 구성 변화**의 영향을 받으니 균형 패널로도 확인하세요.
3. **일부 위기 기관이 없거나 메인 표본 밖에 있어요.** Bear Stearns는 없고, Merrill Lynch & Co는 2011–12년만 있어요. Washington Mutual은 은행이 2001–03년만 있고, 지주회사 2005–07년 자료(자산 약 3,400억 달러)는 후신인 "MR. COOPER GROUP INC." 이름으로 `_all` 파일에 있는 것으로 보여요(메인 표본에는 없음). Lehman Brothers Holdings(2005–07), Wachovia(1997–2007), Hypo Real Estate 등은 메인 표본에 있습니다.
4. **FX·W 변수는 공시 기반이라 결측이 많아요.** 변수마다 커버하는 나라가 다릅니다(5.5절). 통화별 대출은 미국·영국·일본 대형은행에 거의 없어요.
5. **USD 환산:** 모든 금액은 결산일 환율로 환산돼 있습니다. 비율에는 영향이 없지만, **자산 규모와 가중치에는 환율 변동이 섞여** 있어요. `fx_rate_usd`로 현지통화로 되돌릴 수 있습니다.
6. **소유구조(GUO)는 현재 시점 기준**이라 과거 인수합병 이전의 소유관계는 반영되지 않아요.
7. **그룹 중복 제거는 규칙 기반 근사**입니다. 남은 오탐·미탐이 있을 수 있으니, 중요한 결과는 `_all` 파일에서 규칙을 바꿔 확인하세요.

---

## 7. 분석 결과 요약 (`output/`, 모두 글로벌 패널 기준)

레버리지는 연도별 1/99% winsorize, 프랑스 네트워크 회원사(`network_member`)는 제외했습니다.

### Figure 1: 분위별 레버리지 추이
| 그림 | 결과 |
|---|---|
| **미국, 무가중, 1997=100** (`figG1b_us_unweighted.png`) | 상위 5%가 2005년 112, **2007년 129, 2009년 133**까지 오르고, 중앙값은 87–99, 하위 5%는 44–54로 떨어져요. **논문의 "상위 분위만 오른다"는 패턴이 재현**됩니다. |
| 미국, 자산가중, 1997=100 (`figG1_us_aw.png`) | 상위 5%는 2008년까지 97–104로 평탄하고, 중앙값과 상위 10%는 2007–08년에 52–64로 떨어져요. 2001년 커버리지 증가와 대형은행 집중으로 가중치(자산 / 평균 자산)가 기계적으로 흔들리기 때문으로 보입니다. |
| 글로벌, 자산가중·무가중, 2005=100 | 상위 5%가 뚜렷이 오르지 않아요(무가중 2008년 110). 표본이 이미 고점 근처인 2005년에 시작하고, 중국 은행 비중이 커지기 때문으로 보입니다. |

### Figure 2: 위기 전 자산 십분위별 평균 레버리지
- **글로벌 2005–07:** 10.3에서 23.7로 **볼록하게 증가**하고, 자본(equity) 십분위와는 뚜렷한 관계가 없어요. **논문 Stylized fact 1과 같습니다.**
- **미국 1997–2007:** 10.4–12.0으로 거의 평평해서 볼록성이 약해요. 볼록성은 주로 유럽·아시아 대형은행에서 나옵니다.

### Figure 3: 상위 5% 레버리지 은행의 자산 비중 vs FFR
- **미국 1997–2025:** 상관계수 **+0.43(실질), +0.46(명목)**으로 논문(음의 상관)과 **반대**예요. 2005–07년(금리가 높은데 비중 17–21%)이 결과를 좌우하는데, 논문도 이 시기를 이상치로 언급합니다.

### 회귀: 논문 eq. (1)
Lev<sub>it</sub> = β₁ Lev<sub>i,t−1</sub> + β₂ FF<sub>t</sub> + β₃ Top5<sub>it</sub> + β₄ FF<sub>t</sub> × Top5<sub>it</sub> + α<sub>i</sub>. 은행 FE, 은행 단위 클러스터, FF는 실질 FFR입니다.

| 표본 | N (은행) | FF × Top5 | 연도 FE 포함 | FF × Top10 | FF × Top5 (자산가중) |
|---|---|---|---|---|---|
| 미국, 1997–2015 | 3,815 (404) | **−0.864** (p=0.026) | −0.842 (p=0.037) | −0.358 (p=0.082) | +0.278 (p=0.056) |
| 미국, 1997–2025 | 5,923 (415) | **−0.666** (p<0.001) | −0.639 (p<0.001) | −0.376 (p<0.001) | +0.101 (p=0.147) |
| 글로벌, 2005–2025 | 23,254 (1,655) | **−0.368** (p<0.001) | −0.344 (p=0.001) | −0.213 (p<0.001) | −0.087 (p=0.172) |
| 글로벌 (미국 제외) | 18,859 (1,320) | **−0.379** (p=0.001) | −0.352 (p=0.003) | −0.191 (p=0.004) | −0.137 (p=0.071) |

- **고레버리지 은행일수록 레버리지가 실질 FFR에 음(−)으로 더 민감하다**는 Stylized fact 3이 모든 표본에서 재현돼요. Top10 기준에서는 계수가 작아지는데, 이것도 논문과 같습니다.
- **자산가중 Top5 기준은 견고하지 않아요.** 미국은 부호가 양(+)입니다. 논문은 이 버전도 성립한다고 보고하니 차이가 나는 부분이에요.
- 레버리지 상위가 아닌 은행(Top5 = 0)의 FF 계수는 표본에 따라 달라요(미국 1997–2015 +0.130, 미국 1997–2025 −0.012 비유의, 글로벌 약 −0.05). 논문은 유의하지 않다고 보고합니다.

### FX 확장 (글로벌 2005–2025, 연도 FE, X는 1기 시차)
| X | N (은행) | FF × X | FF × Top5 × X |
|---|---|---|---|
| USD 대출 비중 | 2,683 (358) | 0.084 (p=0.53) | −3.27 (p=0.18) |
| 외화대출 비중 | 3,201 (396) | 0.081 (p=0.25) | 0.50 (p=0.71) |
| 해외시장 대출 비중 | 3,668 (571) | 0.043 (p=0.48) | **−0.94 (p=0.076)** |
| FX 파생 명목 / 자산 | 8,387 (840) | **0.033 (p=0.016)** | 1.12 (p=0.12) |

- 해외 노출이 큰 고레버리지 은행이 금리에 더 민감하다는 신호가 약하게(10% 수준) 있지만, 아직 강한 결론은 아니에요. 표본이 작아서 정밀도가 낮습니다.

**회귀 관련 주의**
- 동태 패널(시차 종속변수 + FE)이라 Nickell bias가 있을 수 있어요(T ≈ 20).
- FF는 시계열 변수라 연도 단위 클러스터가 더 보수적이지만, 연도 수가 적어 은행 단위 클러스터를 썼습니다.
- 회계연도와 FFR은 달력연도 기준으로 맞췄어요. 3월 결산 은행은 9개월 차이가 납니다.

---

## 7.5 권역·국가별 이질성과 GFC (`region_gfc.py`, 그림 `figR*`, 표 `region_gfc_tables.tex`)

**질문:** Figure 1의 모습(위기 전 상위 분위만 오르고 위기 후 급락)이 권역·국가마다 다른가? 다르다면 위기 전 자산·자본 집중도 구조와 관련이 있는가?

**설계**
- **기준 연도 2006**(유럽 커버리지가 2005→2006년에 233→330개로 늘어남). 무가중 분위수, 레버리지는 연도별 1/99% winsorize, 프랑스 네트워크 회원사 제외.
- **표본 구성 변화를 없애기 위해 고정 표본(balanced panel)을 씀.** 메인은 (A) 2006–2012년 매년 관측되는 은행. 견고성 확인으로 (B) 2005–2012년 고정 표본(2005=100), (C) 구간 분리(확대는 2006–08년, 디레버리징은 2008–12년 고정 표본)도 계산.
  - (A)는 위기 중 사라진 은행(Lehman 등)이 빠져서 **미국의 확대가 과소평가**돼요. 북미 p95 확대가 (A) +3인데 (C) +17입니다.
- **그룹:** 8개 권역(상위 분위 = p95), 유럽 분할(코어 / 남유럽 GIIPS / 영국, p90), 고정 표본 은행이 18개 이상인 11개국(p90).
- **지표:** 확대(build-up) = max(2007, 2008년 지수) − 100, 디레버리징 = 2012년 지수 − 정점.

**결과 1. Figure 1의 모습은 권역·국가마다 뚜렷이 달라요** (상위 분위, 지수 포인트, 설계 A / B / C)

| 유형 | 그룹 | 위기 전 확대 | 위기 후 디레버리징 |
|---|---|---|---|
| **논문 패턴이 강함** (상위만 오르고 급락) | 일본·선진아시아 (p95) | +36 / +37 / +39 | −43 / −48 / −26 |
| | 일본 (p90) | +35 / +34 / +40 | −34 / −35 / −22 |
| | 독일 (p90) | +24 / +17 / +24 | −45 / −41 / −39 |
| | 영국 (p90) | +34 / +53 / +35 | −46 / −52 / −34 |
| | 유럽 전체 (p95) | +21 / +20 / +26 | −26 / −26 / −21 |
| **약함** | 북미 (p95) | +3 / +7 / +17 | −20 / −25 / −18 |
| | 중국 (p95, 고정 표본 20개) | +16 / – / +11 | −36 / – / −28 |
| **위기 전 확대 없음** | 신흥아시아 (p95) | −12 / +3 / −9 | −10 / −2 / −9 |
| | 중동·아프리카 (p95) | −15 / −14 / −15 | −12 / −7 / −17 |
| **위기 후에도 계속 상승** (유로존 위기) | 이탈리아 (p90) | +59 / +55 / +39 | **+32 / +32 / +29** |
| | 남유럽 GIIPS (p90) | +12 / −2 / +12 | **+23 / +7 / +26** |

- **선진국 중심부(일본, 독일, 영국, 유럽 코어)**에서 논문의 "상위 분위만 오르고 위기 후 급락" 패턴이 가장 선명해요.
- **신흥시장(신흥아시아, 중동·아프리카, 신흥유럽)**에서는 위기 전 상위 분위가 오히려 내려가요.
- **남유럽·이탈리아**는 2008년 이후에도 레버리지가 계속 올라요. 유로존 위기 때 자본 잠식이 이어진 결과로 보입니다.
- 남유럽 전체의 위기 전 확대만 설계에 따라 +12와 −2로 갈려서 견고하지 않아요. 나머지 패턴은 세 설계 모두에서 유지됩니다.

**결과 2. 레버리지가 오른 경로도 달라요** (2006년 레버리지 상위 10% 은행의 자산·자본 증가율, 2006→08, log pts)
- **자산 확대형(능동적, 논문 메커니즘에 가까움):** 독일 ΔA +32 / ΔE −3, 유럽 코어 +23 / +12, 이탈리아 +66 / +37
- **자본 감소형(수동적, 손실):** 일본 +23 / −26, 대만 +6 / −105, 남유럽 +14 / −50
- **북미:** 상위 10% 은행의 자산은 줄고(−3) 자본은 늘었어요(+31). 미국의 확대가 2006년 이전(2004–06)에 일어났고, 고정 표본에서 실패 은행이 빠진 영향으로 보입니다.
- 위기 후 영국·독일·유럽 코어는 **자산 축소 + 자본 확충**, 일본·중국·미국은 **자산은 계속 늘면서 자본을 더 크게 확충**하는 방식으로 레버리지를 낮췄어요.

**결과 3. 단순 집중도는 GFC 때의 움직임을 거의 설명하지 못해요** (20개 그룹 간 Spearman 순위상관, 유럽은 분할 그룹 사용)

| 2006년 구조 지표 | 확대 (A) | 확대 (C) | 디레버리징 (A) | 디레버리징 (C) |
|---|---|---|---|---|
| 자산 CR5 | 0.37 | 0.17 | 0.04 | −0.01 |
| 자본 CR5 | 0.36 | 0.19 | 0.05 | 0.01 |
| 자산 HHI | 0.35 | 0.21 | 0.25 | 0.22 |
| 레버리지 상위 10% 은행의 자산 비중 | −0.17 | −0.10 | −0.18 | −0.11 |
| 규모-레버리지 순위상관 | 0.09 | 0.01 | 0.11 | 0.08 |
| **중앙값 레버리지** | **0.48** | **0.36** | **−0.58** | **−0.59** |

- **자산·자본 집중도(CR5, HHI)는 설계를 바꾸면 관계가 사라져요.**
- 가장 견고한 건 **위기 전 은행 시스템 전체의 레버리지 수준**이에요. 이미 레버리지가 높던 시스템(영국, 독일, 일본, 중국, 유럽 코어)일수록 상위 분위가 더 오르고, 위기 후 더 크게 줄었습니다.
- 다만 그룹이 20개뿐이고 서로 겹치는 경우(권역과 그 안의 국가)도 있어서, 기술통계 수준의 증거예요.

**주의**
- 국가별 고정 표본은 18–184개라, 은행 수가 적은 나라(영국 21개, 중국 18개 등)는 분위수가 1–2개 은행에 좌우될 수 있어요. 그래서 국가·유럽 분할은 p90을 씁니다.
- 일본은 3월 결산이라 "2008"은 2009년 3월 결산이에요.
- 금액은 USD 환산이라, 자산·자본 증가율(결과 2)에는 환율 변동이 섞여 있습니다(레버리지 자체는 영향 없음).

---

## 8. 재현 방법

```bash
# 0) 데이터 경로는 config/paths.example.ini 의 기본값을 씀. 다른 PC면 paths.local.ini 로 복사해 수정
# 1) 패널 생성 (DATA_ROOT/derived/... 에 패널과 MANIFEST.txt 생성)
python run.py build
# 2) 그림·표·집계 CSV (output/ 갱신)
python run.py analysis
# 또는 한 번에
python run.py all
```

- 필요 패키지: `pandas`, `numpy`, `python-calamine`(BankFocus xlsx 읽기용. openpyxl로는 안 열려요), `matplotlib`, `linearmodels`
- `output/tables/cr_tables.tex`는 article 문서라 바로 컴파일됩니다. `table_*.tex`는 표만 들어 있어서 본문에 `\input{}`으로 넣으면 돼요(preamble에 `booktabs`, `threeparttable`, `caption` 필요).
- **BankFocus 원자료(xlsx)와 은행 단위 패널은 이 저장소에 넣지 않아요(.gitignore).** 다시 받으려면 3절의 검색 조건과 export 구성을 따르면 됩니다. Export 옵션은 Keep one record per line, Include the search strategy이고, 두 템플릿 모두 **같은 검색·같은 정렬**로 받아야 해요.

---

## 9. 참고문헌
- Coimbra, N. and Rey, H. (2024). Financial Cycles with Heterogeneous Intermediaries. *Review of Economic Studies*, 91(2), 817–857. Replication files: doi:10.5281/zenodo.7762752
- Duprey, T. and Lé, M. (2016). Bankscope dataset: getting started. (consolidation code 처리 기준)
- Moody's Analytics / Bureau van Dijk, BankFocus.
- FRED, Federal Reserve Bank of St. Louis: FEDFUNDS, CPIAUCSL.

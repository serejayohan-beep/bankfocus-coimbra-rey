# bankfocus-coimbra-rey

BankFocus(옛 Bankscope) 글로벌 은행 패널로 Coimbra & Rey (2024, *REStud*) "Financial Cycles with Heterogeneous Intermediaries"의 레버리지 stylized facts를 재현하고, **권역·국가별 이질성**과 **외화(FX) 노출**로 확장하는 프로젝트입니다.

> **⚠️ BankFocus 데이터는 이 저장소에 없습니다.** 유료 라이선스 데이터라 원자료와 은행 단위 패널은 로컬 `DATA_ROOT`에만 두고, 여기에는 코드·문서·공개자료·집계 결과만 올립니다(`.gitignore`로 차단).

## 구성
| 위치 | 내용 |
|---|---|
| `run.py` | 파이프라인: `build`(원자료 → 패널), `analysis`(패널 → 그림·표) |
| `code/build/` | `global_panel.py`: core·FX export 병합, 클리닝 규칙 13개 |
| `code/analysis/` | `cr_analysis.py`(Figure 1–3, 식 (1) 회귀, FX 확장), `region_gfc.py`(권역·국가별 GFC 이질성) |
| `code/legacy/` | 초기 북미+유럽(v3) 패널 코드. 현재 분석에는 쓰지 않음 |
| `config/` | 데이터 경로 설정 (`paths.example.ini` → `paths.local.ini`로 복사) |
| `data_public/` | FRED 기반 미국 명목·실질 FFR |
| `output/` | 그림(PNG), LaTeX 표(.tex), 권역 집계 CSV |
| `docs/data_README.md` | **데이터 상세 설명서**: 표본, 변수, 클리닝 규칙, 한계, 결과 요약 |
| `docs/decisions.md` | 설계 결정과 이유 |
| `paper/` | 초안 .tex 소스 |

## 실행
```bash
pip install pandas numpy python-calamine matplotlib linearmodels
cp config/paths.example.ini config/paths.local.ini   # Windows: copy
python run.py all
```

## 현재 상태 (2026-10-30)
- 글로벌 패널: 은행 1,853개, 은행-연도 27,823건 (자산 USD 100억 이상, 1997–2025; 북미 외는 2004–05년부터)
- 식 (1)의 FF × Top5는 미국(−0.86)·글로벌(−0.37)에서 음(−)이고 유의 → Stylized fact 3 재현. 자산가중 Top5 버전은 재현 안 됨.
- Figure 1 패턴은 권역별로 크게 다름: 유럽 코어·독일·영국·일본에서 강하고, 미국(시점·표본 문제)·중국·신흥국에서는 약하거나 없음.
- 진행 기록은 로컬 `Project\Coimbra-Rey\PROJECT_LOG.md`, 요약은 claude.ai Project "Coimbra and Rey"의 `claude/status.md`.

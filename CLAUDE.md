# Project instructions for Claude

- **Never commit BankFocus data** (raw xlsx exports, `global_panel_*`/`bankfocus_panel_*` files, any bank-level table). It is licensed data and stays under DATA_ROOT on the user's machine (`C:\Users\USER\Desktop\HG\Archive\Data\Bankfocus`). Only code, docs, public macro data, figures, `.tex` tables and group-level aggregate CSVs go into this repo.
- Deliver documents and tables as `.tex` source only; do not commit compiled PDFs.
- Data paths come from `config/paths.local.ini` or env vars (`BANKFOCUS_DATA`, …) via `run.py`; scripts take paths as CLI arguments. Do not hard-code paths.
- When a derived panel is rebuilt, write it to a new versioned folder under `derived/` with `MANIFEST.txt` (run.py does this) and record the change in `docs/decisions.md`.
- Analysis uses the **global panel only** (TA ≥ USD 10bn, worldwide). `code/legacy/` is the earlier North America + Europe sample, kept for reference.
- Project status lives in the user's local `Project\Coimbra-Rey\PROJECT_LOG.md`; a short summary is mirrored in the claude.ai Project doc `claude/status.md`.
- The user communicates in Korean; repository docs are in Korean with English code/variable names.

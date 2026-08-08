# EncodeBench paper

Single manuscript source for the EncodeBench paper, served at
encodebench.org/paper.

Outputs:

- `public/paper/encodebench.pdf` — the PDF edition
- `public/paper/web/index.html` — the browser edition
- `src/app/paper/page.tsx` — the landing route linking both

## Pipeline

1. **Freeze.** `paper/scripts/freeze_snapshot.py` copies each board's
   `results.json` files and the excluded runs the integrity notes describe
   (as deterministic gzip), the sixteen per-case workspace context
   manifests, and the effort-probe record (as-is) from the run rig
   (`ENCODEBENCH_RIG_DIR` overrides the default), extracts the suite
   manifest at the v3 encoder commit from a local axiom-encode clone via
   `git show` (`ENCODEBENCH_AXIOM_ENCODE_REPO` overrides), and writes
   `manifest.json` with a sha256 for every artifact. The snapshot
   directory is committed; the rig directory it reads is private.
2. **Derive.** `paper/paper_results.py` computes every quantitative claim in
   the manuscript from the frozen snapshot — it re-implements the
   deterministic pieces of `axiom-encode`'s `eval-board` fold — hash-checks
   every frozen file at load, and `verify()` checks the derived headline
   numbers against the board records posted to axiom-encode#1189. The
   manuscript's setup cell calls `verify()`, so a mismatch refuses the
   render.
3. **Render.** From the repo root:

   ```bash
   uv run --project paper python paper/render_paper.py
   ```

   The renderer pins `QUARTO_PYTHON` to the invoking interpreter, renders
   HTML and PDF, and copies both into `public/paper/`. Quarto and a TeX
   distribution must be installed separately; the last known-good render
   used Quarto 1.9.36, TeX Live 2026, and Python 3.14 via the committed
   `uv.lock`.

## Standing rules

- **Board statistics, probe values, and integrity-note numbers derive.**
  The prose interpolates `paper_results` accessors; tables and the figure
  build from the same module. The narrow exception class is harness facts
  the snapshot cannot contain (a hardcoded constant in the audited harness
  source); the manuscript cites those to the audit instead of deriving
  them.
- **The paper refreezes with every board.** A new board means a new
  snapshot directory, updated `PUBLISHED` pins in `paper_results.py`, and a
  re-render — in one change. `SNAPSHOT_DIR_NAME` lives in
  `paper_results.py`; the freeze script and renderer read the same
  constant.
- **Read the rendered tables visually** before shipping; text extraction
  hides clipping.

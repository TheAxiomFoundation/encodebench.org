# EncodeBench paper

Single manuscript source for the EncodeBench paper, served at
encodebench.org/paper.

Outputs:

- `public/paper/encodebench.pdf` — the PDF edition
- `public/paper/web/index.html` — the browser edition
- `src/app/paper/page.tsx` — the landing route linking both

## Pipeline

1. **Freeze.** `paper/scripts/freeze_snapshot.py` copies each board's signed
   `results.json` files (and the effort-probe record) from the run rig into
   `paper/snapshot/<date>/` as deterministic gzip, and writes `manifest.json`
   with a sha256 for every artifact. The snapshot directory is committed.
2. **Derive.** `paper/paper_results.py` computes every quantitative claim in
   the manuscript from the frozen snapshot — it re-implements the
   deterministic pieces of `axiom-encode`'s `eval-board` fold — and
   `verify()` checks the derived headline numbers against the board records
   posted to axiom-encode#1189. The manuscript's setup cell calls `verify()`,
   so a mismatch refuses the render.
3. **Render.** From the repo root:

   ```bash
   uv run --project paper python paper/render_paper.py
   ```

   The renderer pins `QUARTO_PYTHON` to the invoking interpreter, renders
   HTML and PDF, and copies both into `public/paper/`. Quarto and a TeX
   distribution must be installed separately.

## Standing rules

- **No hand-typed numbers.** The prose interpolates `paper_results`
  accessors; tables and the figure build from the same module. If a number
  is not derivable from the frozen snapshot, it does not go in the paper.
- **The paper refreezes with every board.** A new board means a new
  snapshot directory, updated `PUBLISHED` pins in `paper_results.py`, and a
  re-render — in one change.
- **Read the rendered tables visually** before shipping; text extraction
  hides clipping.

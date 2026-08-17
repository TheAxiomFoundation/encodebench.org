"""Fill, render, and publish the EncodeBench paper into the app.

Two steps, deliberately separate. ``fill_paper.py`` runs the computation
(``paper_results`` over the frozen snapshot, ``r.verify()`` first) and writes
the filled ``paper/index.qmd``, ``results/values.json``, and the figure PNGs.
Quarto then renders that filled manuscript with NO engine — no kernel, no
``{python}`` — into the two house editions, and the outputs land in
``public/paper/`` (``web/`` for the browser edition, ``encodebench.pdf`` for
the download), which Next.js serves at encodebench.org/paper.

Run from the repo root::

    uv run --project paper python paper/render_paper.py

Rendering alone needs only Quarto: ``quarto render paper`` from a clean
clone reproduces both editions from the committed filled files.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER_DIR = ROOT / "paper"
PUBLIC_PAPER_DIR = ROOT / "public" / "paper"
PUBLIC_WEB_DIR = PUBLIC_PAPER_DIR / "web"


def find_quarto() -> str:
    path = shutil.which("quarto")
    if path is not None:
        return path
    for candidate in (
        Path.home() / ".local" / "bin" / "quarto",
        Path.home() / "quarto" / "bin" / "quarto",
        Path("/opt/homebrew/bin/quarto"),
        Path("/usr/local/bin/quarto"),
    ):
        if candidate.exists():
            return str(candidate)
    raise SystemExit(
        "Quarto is not installed. Install it, then rerun "
        "`uv run --project paper python paper/render_paper.py`."
    )


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def set_public_web_base_href(destination: Path) -> None:
    """Make paper-relative assets resolve under /paper/web/."""
    index_path = destination / "index.html"
    html = index_path.read_text(encoding="utf-8")
    base_href = '<base href="/paper/web/">'
    if base_href not in html:
        index_path.write_text(
            html.replace("<head>", f"<head>\n{base_href}", 1),
            encoding="utf-8",
        )


def remove_public_web_extras(destination: Path) -> None:
    """Keep only the manuscript files the app serves."""
    for name in [
        "index-preview.html",
        "index.embed.ipynb",
        "index.out.ipynb",
        "index.qmd",
        "index.pdf",
        "_extensions",
        "_tex",
    ]:
        path = destination / name
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def main() -> None:
    quarto = find_quarto()

    env = dict(os.environ)
    tex_bin = Path("/Library/TeX/texbin")
    if tex_bin.exists():
        env["PATH"] = f"{tex_bin}:{env.get('PATH', '')}"

    sys.path.insert(0, str(PAPER_DIR))
    from paper_results import SNAPSHOT_DIR_NAME

    if not (
        PAPER_DIR / "snapshot" / SNAPSHOT_DIR_NAME / "manifest.json"
    ).exists():
        raise SystemExit(
            f"Missing paper/snapshot/{SNAPSHOT_DIR_NAME}. Run "
            "paper/scripts/freeze_snapshot.py first."
        )

    # Step 1: computation → filled manuscript. Refuses on any headline drift.
    subprocess.run(
        [sys.executable, str(PAPER_DIR / "fill_paper.py")],
        check=True,
        cwd=ROOT,
    )
    filled = (PAPER_DIR / "index.qmd").read_text(encoding="utf-8")
    for marker in ("```{python}", "`{python}", "{{"):
        if marker in filled:
            raise SystemExit(
                f"filled manuscript still contains {marker!r}; the render "
                "must not depend on an engine"
            )

    # Step 2: render both house editions with no engine. The project's
    # _quarto.yml carries the formats; a single render produces both.
    out_dir = PAPER_DIR / "out"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    subprocess.run([quarto, "render"], check=True, cwd=PAPER_DIR, env=env)
    html_out_dir = out_dir
    pdf_out_dir = out_dir

    PUBLIC_PAPER_DIR.mkdir(parents=True, exist_ok=True)
    copy_tree(html_out_dir, PUBLIC_WEB_DIR)
    set_public_web_base_href(PUBLIC_WEB_DIR)
    remove_public_web_extras(PUBLIC_WEB_DIR)

    for candidate in (pdf_out_dir / "encodebench.pdf", pdf_out_dir / "index.pdf"):
        if candidate.exists():
            shutil.copy2(candidate, PUBLIC_PAPER_DIR / "encodebench.pdf")
            break
    else:
        raise SystemExit("PDF render produced no encodebench.pdf/index.pdf")

    shutil.rmtree(PAPER_DIR / "out", ignore_errors=True)

    print("Rendered paper assets into public/paper")


if __name__ == "__main__":
    main()

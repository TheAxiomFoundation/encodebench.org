"""Render the EncodeBench paper and publish static assets into the app.

Renders ``paper/index.qmd`` to HTML and PDF and copies the outputs into
``public/paper/`` (``web/`` for the browser edition, ``encodebench.pdf``
for the download), which Next.js serves at encodebench.org/paper. The
render pins the Jupyter engine to the invoking interpreter so it always
executes this checkout's ``paper_results`` against the frozen snapshot.

Run from the repo root::

    uv run --project paper python paper/render_paper.py
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
    for filename in [
        "index-preview.html",
        "index.embed.ipynb",
        "index.out.ipynb",
        "index.qmd",
    ]:
        path = destination / filename
        if path.exists():
            path.unlink()


def main() -> None:
    quarto = find_quarto()

    env = dict(os.environ)
    tex_bin = Path("/Library/TeX/texbin")
    if tex_bin.exists():
        env["PATH"] = f"{tex_bin}:{env.get('PATH', '')}"
    # Pin the Jupyter engine to the invoking virtualenv so the render always
    # executes this checkout's paper_results. QUARTO_PYTHON selects the
    # interpreter; JUPYTER_PREFER_ENV_PATH makes the `python3` kernelspec
    # resolve inside the venv ahead of any user-level kernelspec.
    env["QUARTO_PYTHON"] = sys.executable
    env["JUPYTER_PREFER_ENV_PATH"] = "1"

    if not (PAPER_DIR / "snapshot" / "20260807" / "manifest.json").exists():
        raise SystemExit(
            "Missing paper/snapshot/20260807. Run "
            "paper/scripts/freeze_snapshot.py first."
        )

    html_out_dir = PAPER_DIR / "out" / "web"
    pdf_out_dir = PAPER_DIR / "out" / "pdf"
    for out_dir in (html_out_dir, pdf_out_dir):
        if out_dir.exists():
            shutil.rmtree(out_dir)

    subprocess.run(
        [quarto, "render", "index.qmd", "--to", "html",
         "--output-dir", str(html_out_dir)],
        check=True,
        cwd=PAPER_DIR,
        env=env,
    )
    subprocess.run(
        [quarto, "render", "index.qmd", "--to", "pdf",
         "--output-dir", str(pdf_out_dir)],
        check=True,
        cwd=PAPER_DIR,
        env=env,
    )

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

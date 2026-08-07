"""Freeze the EncodeBench manuscript snapshot from the run rig.

Copies each board's signed ``results.json`` files (plus the effort-probe
record) into ``paper/snapshot/<SNAPSHOT_DIR_NAME>/`` as deterministic gzip
files and writes ``manifest.json`` with a sha256 for every frozen artifact —
both the stored bytes and the decompressed JSON. Re-running on the same
sources produces byte-identical files and the same hashes.

Every quantitative claim in ``paper/index.qmd`` reads from this snapshot
through ``paper/paper_results.py``; nothing in the manuscript is hand-typed
from a summary. The standing rule: the paper refreezes with every new board.

Sources default to the run rig at
``~/TheAxiomFoundation/ops/model-capability-eval/rig`` and can be pointed
elsewhere with ``ENCODEBENCH_RIG_DIR``. Run from the repo root::

    python3 paper/scripts/freeze_snapshot.py
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_DIR_NAME = "20260807"
SNAPSHOT_DIR = REPO_ROOT / "paper" / "snapshot" / SNAPSHOT_DIR_NAME

RIG_DIR = Path(
    os.environ.get(
        "ENCODEBENCH_RIG_DIR",
        Path.home() / "TheAxiomFoundation" / "ops" / "model-capability-eval" / "rig",
    )
)

# Board -> (rig runs directory, runner names). The runner directory names in
# the rig double as the runner names in each results.json manifest.
BOARDS: dict[str, tuple[str, tuple[str, ...]]] = {
    "v1": ("runs.v1-3fd8b063", ("sol", "gpt-5.5", "terra", "luna")),
    "v2": (
        "runs.v2-f60fd29d",
        ("sol", "gpt-5.5", "terra", "luna", "fable", "opus-5"),
    ),
    "v3": ("runs", ("sol", "gpt-5.5", "terra", "luna", "fable", "opus-5")),
}

BOARD_RECORD_URLS = {
    "v1": "https://github.com/TheAxiomFoundation/axiom-encode/issues/1189#issuecomment-5056359224",
    "v2": "https://github.com/TheAxiomFoundation/axiom-encode/issues/1189#issuecomment-5080564313",
    "v3": "https://github.com/TheAxiomFoundation/axiom-encode/issues/1189#issuecomment-5082716028",
}

EFFORT_PROBE_FILE = "effort-probe-results.md"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def deterministic_gzip(data: bytes) -> bytes:
    """Gzip with a zeroed mtime so refreezes are byte-identical."""
    return gzip.compress(data, mtime=0)


def freeze_results(board: str, runs_dir: Path, runner: str) -> dict:
    source = runs_dir / runner / "results.json"
    raw = source.read_bytes()
    payload = json.loads(raw)

    identity = payload["evidence"]["execution_identity"]["axiom_encode"]
    stored = deterministic_gzip(raw)
    dest_rel = f"boards/{board}/{runner}.results.json.gz"
    dest = SNAPSHOT_DIR / dest_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(stored)

    return {
        "runner": runner,
        "model": payload["results"][0]["model"],
        "file": dest_rel,
        "sha256_gz": sha256_bytes(stored),
        "sha256_json": sha256_bytes(raw),
        "schema": payload["schema"],
        "encoder_commit": identity["commit"],
        "encoder_version": identity["version"],
        "run_started_at": payload["evidence"]["run"]["started_at"],
    }


def main() -> None:
    if not RIG_DIR.exists():
        raise SystemExit(f"Rig directory not found: {RIG_DIR}")

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    boards_manifest: dict[str, dict] = {}
    for board, (runs_name, runners) in BOARDS.items():
        runs_dir = RIG_DIR / runs_name
        entries = [freeze_results(board, runs_dir, runner) for runner in runners]

        encoder_commits = {e["encoder_commit"] for e in entries}
        encoder_versions = {e["encoder_version"] for e in entries}
        if len(encoder_commits) != 1 or len(encoder_versions) != 1:
            raise SystemExit(
                f"Board {board} mixes encoder identities: "
                f"{encoder_commits} / {encoder_versions}"
            )

        corpus = json.loads(
            gzip.decompress(
                (SNAPSHOT_DIR / entries[0]["file"]).read_bytes()
            )
        )["evidence"]["corpus"]

        boards_manifest[board] = {
            "source_runs_dir": str(runs_dir),
            "record_url": BOARD_RECORD_URLS[board],
            "encoder_commit": encoder_commits.pop(),
            "encoder_version": encoder_versions.pop(),
            "corpus_release": corpus["corpus_release"],
            "corpus_release_content_sha256": corpus[
                "corpus_release_content_sha256"
            ],
            "runners": entries,
        }

    probe_source = RIG_DIR / EFFORT_PROBE_FILE
    probe_raw = probe_source.read_bytes()
    (SNAPSHOT_DIR / EFFORT_PROBE_FILE).write_bytes(probe_raw)

    manifest = {
        "schema": "encodebench-paper-snapshot/v1",
        "snapshot_dir": SNAPSHOT_DIR_NAME,
        "suite": "EncodeBench UK v1",
        "suite_manifest": "benchmarks/encodebench_uk_v1.yaml",
        "tracking_issue": "https://github.com/TheAxiomFoundation/axiom-encode/issues/1189",
        "boards": boards_manifest,
        "effort_probe": {
            "file": EFFORT_PROBE_FILE,
            "sha256": sha256_bytes(probe_raw),
            "note": (
                "Receiver-behavior probe recorded 2026-07-26: codex "
                "model_reasoning_effort sweep on gpt-5.6-terra and claude "
                "--effort sweep on claude-opus-5, N per level as recorded "
                "in the file."
            ),
        },
    }
    manifest_path = SNAPSHOT_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    total = sum(
        len(board["runners"]) for board in boards_manifest.values()
    )
    print(f"Froze {total} results files across {len(boards_manifest)} boards")
    print(f"Manifest: {manifest_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

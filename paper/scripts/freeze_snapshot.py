"""Freeze the EncodeBench manuscript snapshot from the run rig.

Copies each board's recorded ``results.json`` files, the excluded runs the
integrity notes describe, the per-case workspace context manifests, the
suite manifest at the v3 encoder commit, and the effort-probe record into
``paper/snapshot/<SNAPSHOT_DIR_NAME>/``, and writes ``manifest.json`` with
a sha256 for every frozen artifact. Results files store as deterministic
gzip (both the stored bytes and the decompressed JSON are hashed); the
plain-text artifacts store as-is. Re-running on the same sources produces
byte-identical files and the same hashes.

Board statistics, probe values, and integrity-note numbers in
``paper/index.qmd`` derive from this snapshot through
``paper/paper_results.py``. The standing rule: the paper refreezes with
every new board.

Sources default to the run rig at
``~/TheAxiomFoundation/ops/model-capability-eval/rig`` (override with
``ENCODEBENCH_RIG_DIR``); the suite manifest extracts from a local
axiom-encode clone (override with ``ENCODEBENCH_AXIOM_ENCODE_REPO``). Run
from the repo root::

    python3 paper/scripts/freeze_snapshot.py
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "paper"))
from paper_results import SNAPSHOT_DIR_NAME  # noqa: E402

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
    "v3": (
        "runs.v3-c69a51a4",
        ("sol", "gpt-5.5", "terra", "luna", "fable", "opus-5"),
    ),
}

# Runs that never published: frozen so the paper's integrity notes derive
# from artifacts rather than narrative. Paths are relative to the rig; the
# manifest marks each entry with its exclusion reason. ``format`` selects
# the parser: a finalized ``results.json`` payload, or the per-case
# ``suite-results.jsonl`` rows of a run the finalizer refused.
DISCARDED_RUNS = {
    "v2-opus5-quota-poisoned": {
        "path": "runs.v2-opus5-quota-poisoned/results.json",
        "format": "results-json",
        "reason": (
            "opus-5's first v2 attempt: its encoder and its reviewer drew on "
            "one subscription account, which hit its session limit mid-run. "
            "Discarded as a measurement failure and re-run on split "
            "accounts; the clean re-run is boards/v2/opus-5."
        ),
    },
    "v1-fable-unfinalized": {
        "path": "runs.v1-3fd8b063/fable/suite-results.jsonl",
        "format": "suite-results-jsonl",
        "reason": (
            "fable's completed 2026-07-24 run on the v1 encoder: all 16 "
            "cases ran, but the finalizer refused the run — the "
            "nondeterministic-reviewer revalidation defect PR #1280 later "
            "fixed — so no results.json exists and it could never fold "
            "into board v1, whose record had promised it would. Four "
            "earlier fable attempts died on harness infrastructure (a "
            "malformed MCP config that killed every Claude call, then CLI "
            "auth) and produced no substantive rows."
        ),
    },
}

# Per-case workspace context manifests, one exemplar per case (identical
# across runners and boards per case; every board row binds to one by
# ``context_manifest_sha256``). Frozen so workspace composition — zero
# context files on cold cases, the merged target module riding along on
# repo-augmented ones — derives from the snapshot.
CONTEXT_EXEMPLAR_RUNNER = "sol"

# The suite manifest exactly as the v3 encoder commit pinned it, frozen from
# git so the paper's suite table can be audited against the same text the
# boards ran.
SUITE_YAML_COMMIT = "c69a51a4"
AXIOM_ENCODE_REPO = Path(
    os.environ.get(
        "ENCODEBENCH_AXIOM_ENCODE_REPO",
        Path.home() / "TheAxiomFoundation" / "axiom-encode",
    )
)

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

    discarded_manifest: dict[str, dict] = {}
    for name, spec in DISCARDED_RUNS.items():
        raw = (RIG_DIR / spec["path"]).read_bytes()
        stored = deterministic_gzip(raw)
        suffix = (
            "results.json.gz"
            if spec["format"] == "results-json"
            else "suite-results.jsonl.gz"
        )
        dest_rel = f"discarded/{name}.{suffix}"
        dest = SNAPSHOT_DIR / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(stored)
        discarded_manifest[name] = {
            "file": dest_rel,
            "format": spec["format"],
            "sha256_gz": sha256_bytes(stored),
            "sha256_json": sha256_bytes(raw),
            "discarded": True,
            "reason": spec["reason"],
        }

    context_dir = RIG_DIR / BOARDS["v3"][0] / CONTEXT_EXEMPLAR_RUNNER
    context_manifest_entries: list[dict] = []
    for case_dir in sorted(p for p in context_dir.iterdir() if p.is_dir()):
        if not case_dir.name[:2].isdigit():
            continue
        matches = sorted(
            case_dir.glob("_eval_workspaces/*/*/workspace/context-manifest.json")
        )
        if not matches:
            raise SystemExit(f"No context manifest under {case_dir}")
        raw = matches[0].read_bytes()
        dest_rel = f"context-manifests/{case_dir.name}.json"
        dest = SNAPSHOT_DIR / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        context_manifest_entries.append(
            {
                "case_index": int(case_dir.name[:2]),
                "case_dir": case_dir.name,
                "file": dest_rel,
                "sha256": sha256_bytes(raw),
            }
        )
    if len(context_manifest_entries) != 16:
        raise SystemExit(
            f"Expected 16 context manifests, froze {len(context_manifest_entries)}"
        )

    suite_yaml = subprocess.run(
        [
            "git",
            "-C",
            str(AXIOM_ENCODE_REPO),
            "show",
            f"{SUITE_YAML_COMMIT}:benchmarks/encodebench_uk_v1.yaml",
        ],
        check=True,
        capture_output=True,
    ).stdout
    suite_rel = "encodebench_uk_v1.yaml"
    (SNAPSHOT_DIR / suite_rel).write_bytes(suite_yaml)

    manifest = {
        "schema": "encodebench-paper-snapshot/v1",
        "snapshot_dir": SNAPSHOT_DIR_NAME,
        "suite": "EncodeBench UK v1",
        "suite_manifest": "benchmarks/encodebench_uk_v1.yaml",
        "suite_manifest_frozen": {
            "file": suite_rel,
            "sha256": sha256_bytes(suite_yaml),
            "source_commit": SUITE_YAML_COMMIT,
        },
        "tracking_issue": "https://github.com/TheAxiomFoundation/axiom-encode/issues/1189",
        "boards": boards_manifest,
        "discarded_runs": discarded_manifest,
        "context_manifests": {
            "note": (
                "One exemplar per case, from the v3 "
                f"{CONTEXT_EXEMPLAR_RUNNER} run; every board row binds to "
                "its case's exemplar by context_manifest_sha256, which "
                "paper_results asserts at load."
            ),
            "entries": context_manifest_entries,
        },
        "effort_probe": {
            "file": EFFORT_PROBE_FILE,
            "sha256": sha256_bytes(probe_raw),
            "note": (
                "Receiver-behavior probe recorded 2026-07-26: codex "
                "model_reasoning_effort sweep on gpt-5.6-terra and claude "
                "--effort sweep on claude-opus-5. The file header says N=5 "
                "per level; that holds for the codex arm only — the claude "
                "rows carry three samples per level, and the paper derives "
                "N per arm from the rows."
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

"""Data-driven manuscript values for the EncodeBench paper.

Every quantitative claim in ``paper/index.qmd`` reads from the module-level
instance ``r`` exposed here, mirroring the PolicyBench paper pattern. The
accessors compute from the FROZEN snapshot under ``paper/snapshot/20260807/``
— the boards' ``results.json`` files, one discarded run frozen as such, the
suite manifest at the v3 encoder commit, and the effort-probe record —
never from live rig output, and never from a summary someone typed.

The module is stdlib-only. It re-implements the deterministic pieces of
``axiom-encode``'s ``eval-board`` fold (gate battery, cell classification,
artifact denominators, medians) against the frozen rows, then verifies the
derived headline numbers against the board records posted to
axiom-encode#1189 (``verify()``, called by the manuscript's setup cell).
A mismatch refuses the render instead of publishing drift. Every frozen
file loads through a sha256 check against the manifest.

Cost model, copied from ``ops/model-capability-eval/rig/cost_report.py``:
codex-backend runners price recorded tokens at published July 2026 API rates
(cache reads at 10% of the input rate); Claude-backend runners use the CLI's
own recorded per-call ``actual_cost_usd``, because claude-opus-5 has no
published per-token rate in the reference the harness bundles and inventing
one would be fabrication. All runs were subscription-billed; these are
API-equivalents, and the two bases are labeled wherever they meet.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from statistics import median

PAPER_DIR = Path(__file__).resolve().parent
SNAPSHOT_DIR_NAME = "20260807"
SNAPSHOT_DIR = PAPER_DIR / "snapshot" / SNAPSHOT_DIR_NAME

# (input, output) USD per 1M tokens, July 2026 published API rates; cache
# reads billed at 10% of the input rate. Same table the rig's cost_report.py
# used for the board cost annexes.
RATES = {
    "gpt-5.6-sol": (5.00, 30.00),
    "gpt-5.6-terra": (2.50, 15.00),
    "gpt-5.6-luna": (1.00, 6.00),
    "gpt-5.5": (5.00, 30.00),
}
CLI_REPORTED_MODELS = {"claude-fable-5", "claude-opus-5"}

BOARD_ORDER = ("v1", "v2", "v3")

# Expected headline numbers, pinned from the board records posted to
# axiom-encode#1189 (URLs in the snapshot manifest), plus probe medians from
# the frozen probe record. These are verification targets, not sources: the
# paper renders only derived values, and ``verify()`` refuses the render if
# derivation and record disagree.
PUBLISHED = {
    "v1": {
        "gate": {"sol": 14, "gpt-5.5": 14, "terra": 9, "luna": 5},
        "median_s": {"sol": 43, "gpt-5.5": 46, "terra": 26, "luna": 55},
        "total_cost": 15.11,
    },
    "v2": {
        "gate": {
            "sol": 15,
            "terra": 11,
            "gpt-5.5": 11,
            "fable": 9,
            "luna": 5,
            "opus-5": 2,
        },
        "median_s": {
            "sol": 49,
            "terra": 29,
            "gpt-5.5": 43,
            "fable": 211,
            "luna": 57,
            "opus-5": 38,
        },
        "total_cost": 40.25,
    },
    "v3": {
        "gate": {
            "gpt-5.5": 15,
            "sol": 14,
            "fable": 12,
            "terra": 11,
            "luna": 8,
            "opus-5": 6,
        },
        "median_s": {
            "gpt-5.5": 48,
            "sol": 45,
            "fable": 266,
            "terra": 34,
            "luna": 50,
            "opus-5": 47,
        },
        "timeouts": {"fable": 1},
        "artifacts": {
            "gpt-5.5": 16,
            "sol": 16,
            "fable": 15,
            "terra": 16,
            "luna": 15,
            "opus-5": 16,
        },
        "cost": {
            "gpt-5.5": 5.79,
            "sol": 5.66,
            "fable": 33.02,
            "terra": 2.66,
            "luna": 1.12,
            "opus-5": 3.85,
        },
        "total_cost": 52.09,
    },
}
PUBLISHED_PROBE = {
    ("codex", "medians"): {
        "low": 145.0,
        "medium": 407.0,
        "high": 2243.0,
        "xhigh": 2756.0,
        "ultra": 1685.0,
    },
    ("codex", "walls"): {"low": 20, "medium": 20, "high": 44, "xhigh": 53,
                          "ultra": 106},
    ("claude", "medians"): {
        "low": 0.051,
        "medium": 0.032,
        "high": 0.033,
        "xhigh": 0.03,
        "max": 0.032,
    },
    ("claude", "walls"): {"low": 11, "medium": 11, "high": 12, "xhigh": 13,
                           "max": 12},
    ("claude", "answers"): {"28"},
}

# Advisory source-coverage rates from the v3 board record (#1189): covered
# source numeric occurrences over source occurrences, artifacts only.
PUBLISHED_V3_COVERAGE = {
    "gpt-5.5": 100.0,
    "sol": 100.0,
    "fable": 93.1,
    "terra": 100.0,
    "luna": 94.7,
    "opus-5": 71.2,
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fmt_pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "—"
    return f"{100.0 * numerator / denominator:.1f}%"


def gate_pass(result: dict) -> bool:
    """The deterministic gate battery, as ``eval_board.result_gate_pass``."""
    if (
        result.get("success") is not True
        or result.get("error")
        or result.get("timed_out") is True
    ):
        return False
    metrics = result.get("metrics")
    if metrics is None:
        return False
    return bool(
        metrics.get("compile_pass") is True
        and metrics.get("ci_pass") is True
        and metrics.get("ungrounded_numeric_count") == 0
    )


def cell_state(result: dict) -> str:
    """P/F/T/E classification, as ``eval_board._cell_for_result``."""
    if result.get("failure_kind") == "timeout" or result.get("timed_out") is True:
        return "T"
    metrics = result.get("metrics")
    failed = False
    if metrics is not None:
        failed = (
            metrics.get("compile_pass") is not True
            or metrics.get("ci_pass") is not True
            or metrics.get("ungrounded_numeric_count") != 0
        )
    if result.get("failure_kind") == "validation":
        return "F"
    if failed:
        return "F"
    if (
        result.get("failure_kind") == "error"
        or result.get("success") is not True
        or result.get("error")
        or metrics is None
    ):
        return "E"
    return "P" if gate_pass(result) else "F"


@dataclass
class RunnerStats:
    runner: str
    model: str
    backend: str
    cases: int
    gate_passes: int
    timeouts: int
    artifacts: int
    compile_passes: int
    ci_passes: int
    zero_ungrounded: int
    review_scores: list[float] = field(default_factory=list)
    durations_ms: list[int] = field(default_factory=list)
    completed_durations_ms: list[int] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cli_reported_cost: float = 0.0

    @property
    def gate_label(self) -> str:
        return f"{self.gate_passes}/{self.cases}"

    @property
    def gate_pct(self) -> float:
        return 100.0 * self.gate_passes / self.cases

    @property
    def median_seconds(self) -> int:
        return int(round(median(self.durations_ms) / 1000.0))

    @property
    def completed_median_seconds(self) -> int:
        """Median over rows that produced metrics (excludes killed rows)."""
        return int(round(median(self.completed_durations_ms) / 1000.0))

    @property
    def max_seconds(self) -> int:
        return int(round(max(self.durations_ms) / 1000.0))

    @property
    def compile_rate(self) -> str:
        return _fmt_pct(self.compile_passes, self.artifacts)

    @property
    def ci_rate(self) -> str:
        return _fmt_pct(self.ci_passes, self.artifacts)

    @property
    def grounded_rate(self) -> str:
        return _fmt_pct(self.zero_ungrounded, self.artifacts)

    @property
    def review_score_count(self) -> int:
        return len(self.review_scores)

    @property
    def mean_review_score(self) -> float | None:
        if not self.review_scores:
            return None
        return sum(self.review_scores) / len(self.review_scores)

    @property
    def cost(self) -> float:
        if self.model in RATES:
            rate_in, rate_out = RATES[self.model]
            return (
                self.input_tokens / 1e6 * rate_in
                + self.output_tokens / 1e6 * rate_out
                + self.cache_read_tokens / 1e6 * rate_in * 0.10
            )
        if self.model in CLI_REPORTED_MODELS:
            return self.cli_reported_cost
        raise ValueError(f"No cost basis for {self.model}")

    @property
    def cost_basis(self) -> str:
        return "rate table" if self.model in RATES else "CLI-reported"

    @property
    def cost_per_pass(self) -> float:
        return self.cost / self.gate_passes


def _stats_for(runner: str, rows: list[dict]) -> RunnerStats:
    s = RunnerStats(
        runner=runner,
        model=rows[0]["model"],
        backend=rows[0]["backend"],
        cases=len(rows),
        gate_passes=sum(1 for r in rows if gate_pass(r)),
        timeouts=sum(1 for r in rows if cell_state(r) == "T"),
        artifacts=0,
        compile_passes=0,
        ci_passes=0,
        zero_ungrounded=0,
    )
    for r in rows:
        duration = r.get("duration_ms")
        has_duration = isinstance(duration, int) and not isinstance(duration, bool)
        if has_duration:
            s.durations_ms.append(duration)
        s.input_tokens += r.get("input_tokens") or 0
        s.output_tokens += r.get("output_tokens") or 0
        s.cache_read_tokens += r.get("cache_read_tokens") or 0
        s.cli_reported_cost += r.get("actual_cost_usd") or 0.0
        metrics = r.get("metrics")
        if metrics is None:
            continue
        s.artifacts += 1
        if has_duration:
            s.completed_durations_ms.append(duration)
        if metrics.get("compile_pass") is True:
            s.compile_passes += 1
        if metrics.get("ci_pass") is True:
            s.ci_passes += 1
        if metrics.get("ungrounded_numeric_count") == 0:
            s.zero_ungrounded += 1
        score = metrics.get("generalist_review_score")
        if isinstance(score, (int, float)):
            s.review_scores.append(float(score))
    return s


class PaperResults:
    """Derived, formatted values for the manuscript."""

    @cached_property
    def manifest(self) -> dict:
        return json.loads((SNAPSHOT_DIR / "manifest.json").read_text())

    def _load_verified(self, rel_path: str, expected_sha: str) -> bytes:
        raw = (SNAPSHOT_DIR / rel_path).read_bytes()
        if _sha256(raw) != expected_sha:
            raise ValueError(f"Hash mismatch (stored): {rel_path}")
        return raw

    @cached_property
    def boards(self) -> dict[str, dict[str, dict]]:
        """board -> runner -> full results.json payload, hash-verified."""
        out: dict[str, dict[str, dict]] = {}
        for board, meta in self.manifest["boards"].items():
            runners: dict[str, dict] = {}
            for entry in meta["runners"]:
                stored = self._load_verified(entry["file"], entry["sha256_gz"])
                raw = gzip.decompress(stored)
                if _sha256(raw) != entry["sha256_json"]:
                    raise ValueError(f"Hash mismatch (content): {entry['file']}")
                runners[entry["runner"]] = json.loads(raw)
            out[board] = runners
        return out

    @cached_property
    def discarded(self) -> dict[str, dict | list]:
        """Excluded runs, hash-verified; frozen so integrity notes derive.

        ``results-json`` entries parse to the payload dict;
        ``suite-results-jsonl`` entries parse to the list of per-case
        result rows a never-finalized run left behind.
        """
        out: dict[str, dict | list] = {}
        for name, entry in self.manifest.get("discarded_runs", {}).items():
            stored = self._load_verified(entry["file"], entry["sha256_gz"])
            raw = gzip.decompress(stored)
            if _sha256(raw) != entry["sha256_json"]:
                raise ValueError(f"Hash mismatch (content): {entry['file']}")
            if entry.get("format") == "suite-results-jsonl":
                out[name] = [
                    json.loads(line)["result"]
                    for line in raw.decode("utf-8").splitlines()
                    if line.strip()
                ]
            else:
                out[name] = json.loads(raw)
        return out

    @cached_property
    def suite_yaml(self) -> str:
        """The suite manifest at the v3 encoder commit, hash-verified."""
        entry = self.manifest["suite_manifest_frozen"]
        return self._load_verified(entry["file"], entry["sha256"]).decode(
            "utf-8"
        )

    @cached_property
    def context_manifests(self) -> dict[int, dict]:
        """Case index -> parsed workspace context manifest, hash-verified.

        Loading also proves the binding: every board row's
        ``context_manifest_sha256`` must equal its case's exemplar hash
        (rows the harness killed before a workspace existed carry None).
        """
        exemplars: dict[int, dict] = {}
        shas: dict[int, str] = {}
        for entry in self.manifest["context_manifests"]["entries"]:
            raw = self._load_verified(entry["file"], entry["sha256"])
            exemplars[entry["case_index"]] = json.loads(raw)
            shas[entry["case_index"]] = entry["sha256"]
        for board, runners in self.boards.items():
            for runner, payload in runners.items():
                for row in payload["results"]:
                    sha = row.get("context_manifest_sha256")
                    index = row["eval_case"]["index"]
                    if sha is not None and sha != shas[index]:
                        raise ValueError(
                            f"{board}/{runner} case {index} context manifest "
                            "does not match the frozen exemplar"
                        )
        return exemplars

    @cached_property
    def workspace_composition(self) -> dict[int, dict]:
        """Case index -> {n_context_files, kinds} from the frozen manifests."""
        out: dict[int, dict] = {}
        for index, manifest in self.context_manifests.items():
            files = manifest.get("context_files") or []
            out[index] = {
                "n_context_files": len(files),
                "kinds": {f.get("kind") for f in files},
            }
        return out

    @cached_property
    def cold_context_file_counts(self) -> set[int]:
        """Distinct context-file counts across the thirteen cold cases."""
        return {
            comp["n_context_files"]
            for index, comp in self.workspace_composition.items()
            if index <= 13
        }

    @cached_property
    def repo_augmented_composition(self) -> dict[int, dict]:
        """The three oracle-path cases' workspace contents."""
        return {
            index: comp
            for index, comp in self.workspace_composition.items()
            if index >= 14
        }

    def board_meta(self, board: str) -> dict:
        return self.manifest["boards"][board]

    # ------------------------------------------------------------------
    # Per-runner statistics
    # ------------------------------------------------------------------

    @cached_property
    def stats(self) -> dict[str, dict[str, RunnerStats]]:
        return {
            board: {
                runner: _stats_for(runner, payload["results"])
                for runner, payload in runners.items()
            }
            for board, runners in self.boards.items()
        }

    def ranked(self, board: str) -> list[RunnerStats]:
        return sorted(
            self.stats[board].values(),
            key=lambda s: (-s.gate_passes, s.median_seconds),
        )

    def total_cost(self, board: str) -> float:
        return sum(s.cost for s in self.stats[board].values())

    @cached_property
    def backends_used(self) -> set[str]:
        """Every backend that produced a board row, across all boards."""
        return {
            r["backend"]
            for runners in self.boards.values()
            for payload in runners.values()
            for r in payload["results"]
        }

    # ------------------------------------------------------------------
    # Grids and cross-board views
    # ------------------------------------------------------------------

    def case_names(self, board: str = "v3") -> list[tuple[int, str]]:
        payload = next(iter(self.boards[board].values()))
        return [
            (r["eval_case"]["index"], r["eval_case"]["name"])
            for r in payload["results"]
        ]

    def case_citations(self, board: str = "v3") -> dict[int, str]:
        """Case index -> corpus citation path, from the frozen rows."""
        payload = next(iter(self.boards[board].values()))
        return {
            r["eval_case"]["index"]: r["eval_case"]["corpus_citation_path"]
            for r in payload["results"]
        }

    def grid(self, board: str) -> list[dict]:
        """Per-case rows: {index, name, cells: {runner: letter}}."""
        order = [s.runner for s in self.ranked(board)]
        by_runner = {
            runner: {r["eval_case"]["index"]: r for r in payload["results"]}
            for runner, payload in self.boards[board].items()
        }
        rows = []
        for index, name in self.case_names(board):
            rows.append(
                {
                    "index": index,
                    "name": name,
                    "cells": {
                        runner: cell_state(by_runner[runner][index])
                        for runner in order
                    },
                }
            )
        return rows

    @cached_property
    def gate_by_board(self) -> dict[str, dict[str, int]]:
        """runner -> board -> gate passes (absent board omitted)."""
        out: dict[str, dict[str, int]] = {}
        for board in BOARD_ORDER:
            for runner, s in self.stats[board].items():
                out.setdefault(runner, {})[board] = s.gate_passes
        return out

    @cached_property
    def v2_v3_deltas(self) -> dict[str, int]:
        return {
            runner: self.stats["v3"][runner].gate_passes
            - self.stats["v2"][runner].gate_passes
            for runner in self.stats["v3"]
        }

    @cached_property
    def v2_v3_transitions(self) -> dict[str, int]:
        """Case-level gate transitions between v2 and v3, split by kind.

        ``kill_to_pass`` counts fable's harness-killed v2 rows (no artifact,
        600-second ceiling in the recorded error) that pass on v3 — movement
        mechanically explained by the timeout fix rather than by either
        sampling noise or validator change.
        """
        counts = {"fail_to_pass": 0, "pass_to_fail": 0, "kill_to_pass": 0}
        for runner in self.stats["v3"]:
            v2_rows = {
                r["eval_case"]["index"]: r
                for r in self.boards["v2"][runner]["results"]
            }
            v3_rows = {
                r["eval_case"]["index"]: r
                for r in self.boards["v3"][runner]["results"]
            }
            for index, v2_row in v2_rows.items():
                v3_row = v3_rows[index]
                before, after = gate_pass(v2_row), gate_pass(v3_row)
                if before and not after:
                    counts["pass_to_fail"] += 1
                elif after and not before:
                    if _is_600s_kill(v2_row):
                        counts["kill_to_pass"] += 1
                    else:
                        counts["fail_to_pass"] += 1
        return counts

    @cached_property
    def extremes_yardstick(self) -> dict[str, int]:
        """Smallest leader-vs-tail gap on v3 against the largest v2→v3 delta."""
        v3 = self.stats["v3"]
        leaders = {"gpt-5.5", "sol"}
        tail = {"luna", "opus-5"}
        min_gap = min(
            v3[a].gate_passes - v3[b].gate_passes for a in leaders for b in tail
        )
        max_delta = max(abs(d) for d in self.v2_v3_deltas.values())
        return {"min_gap": min_gap, "max_delta": max_delta}

    def runner_flips(self, runner: str) -> dict[str, int]:
        """One runner's v2→v3 case-level gate flips."""
        v2_rows = {
            r["eval_case"]["index"]: r
            for r in self.boards["v2"][runner]["results"]
        }
        v3_rows = {
            r["eval_case"]["index"]: r
            for r in self.boards["v3"][runner]["results"]
        }
        f2p = sum(
            1
            for i, r in v2_rows.items()
            if not gate_pass(r) and gate_pass(v3_rows[i])
        )
        p2f = sum(
            1
            for i, r in v2_rows.items()
            if gate_pass(r) and not gate_pass(v3_rows[i])
        )
        return {"fail_to_pass": f2p, "pass_to_fail": p2f}

    @cached_property
    def flip_binomial_p(self) -> float:
        """Two-sided exact binomial p for the non-mechanical flip split."""
        from math import comb

        k = self.v2_v3_transitions["fail_to_pass"]
        n = k + self.v2_v3_transitions["pass_to_fail"]
        tail = sum(comb(n, i) for i in range(k, n + 1)) / 2**n
        return min(1.0, 2 * tail)

    def cold_gate_passes(self, runner: str) -> int:
        """Gate passes on the thirteen cold cases (indices 1–13), v3."""
        return sum(
            1
            for r in self.boards["v3"][runner]["results"]
            if r["eval_case"]["index"] <= 13 and gate_pass(r)
        )

    def coverage_pct(self, runner: str, board: str = "v3") -> float:
        """Advisory source-coverage: covered over total source numeric
        occurrences, summed across the runner's artifacts."""
        covered = 0
        total = 0
        for r in self.boards[board][runner]["results"]:
            metrics = r.get("metrics")
            if metrics is None:
                continue
            covered += metrics.get(
                "covered_source_numeric_occurrence_count"
            ) or 0
            total += metrics.get("source_numeric_occurrence_count") or 0
        return 100.0 * covered / total if total else float("nan")

    # ------------------------------------------------------------------
    # Grounding scan totals
    # ------------------------------------------------------------------

    def _grounding_totals_for(self, boards: tuple[str, ...]) -> dict[str, int]:
        artifacts = 0
        literals = 0
        flagged_artifacts = 0
        for board in boards:
            for payload in self.boards[board].values():
                for r in payload["results"]:
                    metrics = r.get("metrics")
                    if metrics is None:
                        continue
                    artifacts += 1
                    literals += (metrics.get("grounded_numeric_count") or 0) + (
                        metrics.get("ungrounded_numeric_count") or 0
                    )
                    if metrics.get("ungrounded_numeric_count") != 0:
                        flagged_artifacts += 1
        return {
            "artifacts": artifacts,
            "literals": literals,
            "flagged_artifacts": flagged_artifacts,
        }

    @cached_property
    def grounding_totals(self) -> dict[str, int]:
        """Literals the grounding scan checked, all boards pooled."""
        return self._grounding_totals_for(BOARD_ORDER)

    @cached_property
    def grounding_totals_v3(self) -> dict[str, int]:
        """Literals the grounding scan checked on board v3 alone."""
        return self._grounding_totals_for(("v3",))

    # ------------------------------------------------------------------
    # Timeout policy (v3 execution identity) and the v2 fable truncation
    # ------------------------------------------------------------------

    @cached_property
    def v3_timeout_policy(self) -> dict:
        """The recorded v3 runner_timeouts, identical across runners."""
        policies = {
            json.dumps(
                payload["evidence"]["execution_identity"]["runner_timeouts"],
                sort_keys=True,
            )
            for payload in self.boards["v3"].values()
        }
        (policy,) = policies
        parsed = json.loads(policy)
        case_budgets = {
            payload["evidence"]["execution_identity"]["case_timeout_seconds"]
            for payload in self.boards["v3"].values()
        }
        (case_budget,) = case_budgets
        return {
            "case_budget_s": int(case_budget),
            "claude_wall_s": int(parsed["claude"]["wall_seconds"]),
            "codex_short_wall_s": int(
                parsed["codex"]["short_source"]["wall_seconds"]
            ),
            "codex_short_idle_s": int(
                parsed["codex"]["short_source"]["idle_seconds"]
            ),
            "codex_long_wall_s": int(
                parsed["codex"]["long_source"]["wall_seconds"]
            ),
            "codex_long_idle_s": int(
                parsed["codex"]["long_source"]["idle_seconds"]
            ),
        }

    @cached_property
    def v3_codex_max_seconds(self) -> int:
        """Longest codex-backend case on v3, all rows."""
        return max(
            s.max_seconds
            for s in self.stats["v3"].values()
            if s.backend == "codex"
        )

    @cached_property
    def v2_fable(self) -> dict:
        rows = self.boards["v2"]["fable"]["results"]
        killed = [r for r in rows if _is_600s_kill(r)]
        completed = [r for r in rows if r.get("metrics") is not None]
        assert len(killed) + len(completed) == len(rows)
        return {
            "killed": len(killed),
            "completed": len(completed),
            "completed_passes": sum(1 for r in completed if gate_pass(r)),
            "completed_median_s": self.stats["v2"][
                "fable"
            ].completed_median_seconds,
        }

    @cached_property
    def v3_fable_timeout(self) -> dict:
        rows = self.boards["v3"]["fable"]["results"]
        (row,) = [r for r in rows if r.get("timed_out") is True]
        return {
            "case": row["eval_case"]["name"],
            "reason": row.get("timeout_reason"),
            "seconds": int(row.get("timeout_seconds") or 0),
        }

    # ------------------------------------------------------------------
    # Integrity notes, derived from frozen artifacts
    # ------------------------------------------------------------------

    @cached_property
    def fable_v1(self) -> dict:
        """fable's completed, never-finalized run on the v1 encoder."""
        rows = self.discarded["v1-fable-unfinalized"]
        assert isinstance(rows, list)
        kills = [r for r in rows if _is_600s_kill(r)]
        durations = [
            r["duration_ms"]
            for r in rows
            if isinstance(r.get("duration_ms"), int)
            and not isinstance(r.get("duration_ms"), bool)
        ]
        return {
            "cases": len(rows),
            "gate_passes": sum(1 for r in rows if gate_pass(r)),
            "artifacts": sum(1 for r in rows if r.get("metrics") is not None),
            "kills_600s": len(kills),
            "median_s": int(round(median(durations) / 1000.0)),
        }

    @cached_property
    def discarded_opus5(self) -> dict:
        payload = self.discarded["v2-opus5-quota-poisoned"]
        rows = payload["results"]
        limit_rows = [
            r for r in rows if "session limit" in str(r.get("error") or "")
        ]
        durations = sorted(
            (r.get("duration_ms") or 0) / 1000.0 for r in limit_rows
        )
        return {
            "cases": len(rows),
            "gate_passes": sum(1 for r in rows if gate_pass(r)),
            "limit_errors": len(limit_rows),
            "limit_median_s": round(median(durations), 1) if durations else None,
        }

    @cached_property
    def v2_opus5_durations(self) -> dict:
        s = self.stats["v2"]["opus-5"]
        return {
            "min_s": int(round(min(s.durations_ms) / 1000.0)),
            "max_s": int(round(max(s.durations_ms) / 1000.0)),
        }

    @cached_property
    def v2_luna_review_coverage(self) -> int:
        return self.stats["v2"]["luna"].review_score_count

    # ------------------------------------------------------------------
    # Case 04 and expression dates
    # ------------------------------------------------------------------

    @cached_property
    def case04(self) -> dict:
        """income_tax_rate_bands across v1+v2 (fails) and v3 (passers)."""
        total_runs = 0
        fails = 0
        kills = 0
        for board in ("v1", "v2"):
            for payload in self.boards[board].values():
                (row,) = [
                    r
                    for r in payload["results"]
                    if r["eval_case"]["name"] == "income_tax_rate_bands"
                ]
                total_runs += 1
                if not gate_pass(row):
                    fails += 1
                    if _is_600s_kill(row):
                        kills += 1
        passers = []
        for s in self.ranked("v3"):
            (row,) = [
                r
                for r in self.boards["v3"][s.runner]["results"]
                if r["eval_case"]["name"] == "income_tax_rate_bands"
            ]
            if gate_pass(row):
                passers.append(s.runner)
        assert fails == total_runs
        return {
            "runs_v1_v2": total_runs,
            "fails": fails,
            "kills": kills,
            "attempts_failed": fails - kills,
            "v3_passers": passers,
        }

    @cached_property
    def v3_expression_dates(self) -> set[str]:
        """Per-provision expression dates recorded in the v3 attestations."""
        return {
            r["source_attestation"]["expression_date"]
            for payload in self.boards["v3"].values()
            for r in payload["results"]
        }

    # ------------------------------------------------------------------
    # Effort probe (frozen markdown record, hash-verified and parsed)
    # ------------------------------------------------------------------

    @cached_property
    def effort_probe(self) -> dict[str, list[dict]]:
        entry = self.manifest["effort_probe"]
        raw = self._load_verified(entry["file"], entry["sha256"])
        text = raw.decode("utf-8")
        blocks: dict[str, list[dict]] = {}
        current: list[dict] | None = None
        for line in text.splitlines():
            if line.startswith("## codex"):
                current = blocks.setdefault("codex", [])
            elif line.startswith("## claude"):
                current = blocks.setdefault("claude", [])
            elif current is not None and line.startswith("|"):
                cols = [c.strip() for c in line.strip("|").split("|")]
                if len(cols) < 4 or cols[0] in {"level", ""} or set(cols[0]) == {"-"}:
                    continue
                level, metric, wall, answers = cols[0], cols[1], cols[2], cols[3]
                m = re.match(r"([\d.]+)\s*\(all: ([^)]+)\)", metric)
                current.append(
                    {
                        "level": level,
                        "median": float(m.group(1)) if m else float(metric),
                        "all": (
                            [float(x) for x in m.group(2).split()] if m else []
                        ),
                        "wall_s": int(wall),
                        "answers": answers.split(),
                    }
                )
        return blocks

    def probe_level(self, backend: str, level: str) -> dict:
        (row,) = [x for x in self.effort_probe[backend] if x["level"] == level]
        return row

    def probe_n(self, backend: str) -> int:
        """Samples per level, derived from the rows (the header lies)."""
        ns = {len(row["answers"]) for row in self.effort_probe[backend]}
        (n,) = ns
        return n

    @cached_property
    def claude_probe_answer_sets(self) -> set[str]:
        """Distinct answers claude-opus-5 gave across every probe level."""
        return {
            a
            for row in self.effort_probe["claude"]
            for a in row["answers"]
        }

    @cached_property
    def claude_probe_cost_medians(self) -> dict[str, float]:
        return {
            row["level"]: row["median"] for row in self.effort_probe["claude"]
        }

    @cached_property
    def claude_probe_wall_range(self) -> tuple[int, int]:
        walls = [row["wall_s"] for row in self.effort_probe["claude"]]
        return (min(walls), max(walls))

    @cached_property
    def claude_probe_low_samples(self) -> tuple[float, float]:
        """The low level's sample range across its three draws."""
        samples = self.probe_level("claude", "low")["all"]
        return (min(samples), max(samples))

    # ------------------------------------------------------------------
    # Formatted fragments for inline prose
    # ------------------------------------------------------------------

    @staticmethod
    def money(x: float) -> str:
        return f"${x:.2f}"

    @staticmethod
    def money3(x: float) -> str:
        return f"${x:.3f}"

    @staticmethod
    def thousands(x: float) -> str:
        return f"{x:,.0f}"

    def encoder(self, board: str) -> str:
        meta = self.board_meta(board)
        return f"{meta['encoder_version']} ({meta['encoder_commit'][:8]})"

    def encoder_version(self, board: str) -> str:
        return self.board_meta(board)["encoder_version"]

    def run_date(self, board: str) -> str:
        started = self.board_meta(board)["runners"][0]["run_started_at"]
        return started.split("T")[0]

    @cached_property
    def corpus_release(self) -> str:
        return self.board_meta("v3")["corpus_release"]

    @cached_property
    def fable_cost_multiple_of_sol(self) -> str:
        v3 = self.stats["v3"]
        return f"{v3['fable'].cost / v3['sol'].cost:.1f}"

    # ------------------------------------------------------------------
    # Verification against the published board records
    # ------------------------------------------------------------------

    def verify(self) -> str:
        problems: list[str] = []
        for board, expected in PUBLISHED.items():
            stats = self.stats[board]
            for runner, want in expected["gate"].items():
                got = stats[runner].gate_passes
                if got != want:
                    problems.append(
                        f"{board} {runner} gate {got} != published {want}"
                    )
            for runner, want in expected["median_s"].items():
                got = stats[runner].median_seconds
                if got != want:
                    problems.append(
                        f"{board} {runner} median {got}s != published {want}s"
                    )
            for runner, want in expected.get("timeouts", {}).items():
                got = stats[runner].timeouts
                if got != want:
                    problems.append(
                        f"{board} {runner} timeouts {got} != published {want}"
                    )
            for runner, want in expected.get("artifacts", {}).items():
                got = stats[runner].artifacts
                if got != want:
                    problems.append(
                        f"{board} {runner} artifacts {got} != published {want}"
                    )
            for runner, want in expected.get("cost", {}).items():
                got = round(stats[runner].cost, 2)
                if abs(got - want) > 0.005:
                    problems.append(
                        f"{board} {runner} cost {got} != published {want}"
                    )
            total = round(self.total_cost(board), 2)
            if abs(total - expected["total_cost"]) > 0.005:
                problems.append(
                    f"{board} total cost {total} != published "
                    f"{expected['total_cost']}"
                )
        for backend in ("codex", "claude"):
            for row in self.effort_probe[backend]:
                if row["median"] != PUBLISHED_PROBE[(backend, "medians")].get(
                    row["level"]
                ):
                    problems.append(
                        f"{backend} probe {row['level']} median drifted"
                    )
                if row["wall_s"] != PUBLISHED_PROBE[(backend, "walls")].get(
                    row["level"]
                ):
                    problems.append(
                        f"{backend} probe {row['level']} wall drifted"
                    )
        if self.claude_probe_answer_sets != PUBLISHED_PROBE[("claude", "answers")]:
            problems.append("claude probe answers drifted from the record")
        for runner, want in PUBLISHED_V3_COVERAGE.items():
            got = round(self.coverage_pct(runner), 1)
            if abs(got - want) > 0.05:
                problems.append(
                    f"v3 {runner} coverage {got} != published {want}"
                )
        # Touching these proves the suite yaml's hash and the per-row
        # context-manifest binding; both raise on mismatch.
        assert self.suite_yaml
        assert self.workspace_composition
        if self.cold_context_file_counts != {0}:
            problems.append(
                "cold cases carry context files: "
                f"{self.cold_context_file_counts}"
            )
        if problems:
            raise AssertionError(
                "Derived values disagree with the published board records:\n"
                + "\n".join(problems)
            )
        return (
            f"verified against published records: "
            f"{sum(len(e['gate']) for e in PUBLISHED.values())} runner gate "
            f"counts, medians, v3 artifacts/timeouts/costs/coverage, the "
            f"full probe tables, and the context-manifest binding"
        )


def _is_600s_kill(result: dict) -> bool:
    """A v2 Claude-path harness kill: no artifact, 600s ceiling in the error."""
    return (
        result.get("metrics") is None
        and result.get("success") is not True
        and "600 seconds" in str(result.get("error") or "")
    )


r = PaperResults()


if __name__ == "__main__":
    print(r.verify())
    for board in BOARD_ORDER:
        print(f"\n{board} — encoder {r.encoder(board)} — run {r.run_date(board)}")
        for s in r.ranked(board):
            print(
                f"  {s.runner:<8} {s.gate_label:>5} ({s.gate_pct:.1f}%)  "
                f"T={s.timeouts} artifacts={s.artifacts} "
                f"compile={s.compile_rate} ci={s.ci_rate} "
                f"grounded={s.grounded_rate} median={s.median_seconds}s "
                f"cost={r.money(s.cost)}"
            )
        print(f"  total {r.money(r.total_cost(board))}")
    print(f"\nv2→v3 deltas: {r.v2_v3_deltas}")
    print(f"v2→v3 transitions: {r.v2_v3_transitions}")
    print(f"flip binomial p: {r.flip_binomial_p:.3f}")
    print(f"gpt-5.5 flips: {r.runner_flips('gpt-5.5')}")
    print(f"extremes yardstick: {r.extremes_yardstick}")
    print(f"grounding totals: {r.grounding_totals}")
    print(f"grounding totals v3: {r.grounding_totals_v3}")
    print(
        "cold v3 passes: "
        + ", ".join(
            f"{s.runner} {r.cold_gate_passes(s.runner)}/13"
            for s in r.ranked("v3")
        )
    )
    print(
        "v3 coverage: "
        + ", ".join(
            f"{s.runner} {r.coverage_pct(s.runner):.1f}%"
            for s in r.ranked("v3")
        )
    )
    print(f"workspace composition (14-16): {r.repo_augmented_composition}")
    print(f"fable v1 (unfinalized): {r.fable_v1}")
    print(f"v3 timeout policy: {r.v3_timeout_policy}")
    print(f"v3 codex max: {r.v3_codex_max_seconds}s")
    print(f"v2 fable: {r.v2_fable}")
    print(f"v3 fable timeout: {r.v3_fable_timeout}")
    print(f"case04: {r.case04}")
    print(f"discarded opus-5: {r.discarded_opus5}")
    print(f"v2 opus-5 durations: {r.v2_opus5_durations}")
    print(f"v2 luna review coverage: {r.v2_luna_review_coverage}")
    print(f"v3 expression dates: {r.v3_expression_dates}")
    print(f"backends used: {r.backends_used}")
    print(f"probe N: codex={r.probe_n('codex')} claude={r.probe_n('claude')}")
    print(f"claude probe cost medians: {r.claude_probe_cost_medians}")

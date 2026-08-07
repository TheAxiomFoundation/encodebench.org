"""Data-driven manuscript values for the EncodeBench paper.

Every quantitative claim in ``paper/index.qmd`` reads from the module-level
instance ``r`` exposed here, mirroring the PolicyBench paper pattern. The
accessors compute from the FROZEN snapshot under ``paper/snapshot/20260807/``
— sixteen signed ``results.json`` files across three boards, plus the
effort-probe record — never from live rig output, and never from a summary
someone typed.

The module is stdlib-only. It re-implements the deterministic pieces of
``axiom-encode``'s ``eval-board`` fold (gate battery, cell classification,
artifact denominators, medians) against the frozen rows, then verifies the
derived headline numbers against the board records posted to
axiom-encode#1189 (``verify()``, called by the manuscript's setup cell).
A mismatch refuses the render instead of publishing drift.

Cost model, copied from ``ops/model-capability-eval/rig/cost_report.py``:
codex-backend runners price recorded tokens at published July 2026 API rates
(cache reads at 10% of input); Claude-backend runners use the CLI's own
recorded per-call ``actual_cost_usd``, because claude-opus-5 has no published
per-token rate in the reference the rig bundles and inventing one would be
fabrication. All runs were subscription-billed; these are API-equivalents.
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
SNAPSHOT_DIR = PAPER_DIR / "snapshot" / "20260807"

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
# axiom-encode#1189 (URLs in the snapshot manifest). These are verification
# targets, not sources: the paper renders only derived values, and
# ``verify()`` refuses the render if derivation and record disagree.
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
    cases: int
    gate_passes: int
    timeouts: int
    artifacts: int
    compile_passes: int
    ci_passes: int
    zero_ungrounded: int
    review_scores: list[float] = field(default_factory=list)
    durations_ms: list[int] = field(default_factory=list)
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
    def compile_rate(self) -> str:
        return _fmt_pct(self.compile_passes, self.artifacts)

    @property
    def ci_rate(self) -> str:
        return _fmt_pct(self.ci_passes, self.artifacts)

    @property
    def grounded_rate(self) -> str:
        return _fmt_pct(self.zero_ungrounded, self.artifacts)

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


class PaperResults:
    """Derived, formatted values for the manuscript."""

    @cached_property
    def manifest(self) -> dict:
        return json.loads((SNAPSHOT_DIR / "manifest.json").read_text())

    @cached_property
    def boards(self) -> dict[str, dict[str, dict]]:
        """board -> runner -> full results.json payload, hash-verified."""
        out: dict[str, dict[str, dict]] = {}
        for board, meta in self.manifest["boards"].items():
            runners: dict[str, dict] = {}
            for entry in meta["runners"]:
                stored = (SNAPSHOT_DIR / entry["file"]).read_bytes()
                if _sha256(stored) != entry["sha256_gz"]:
                    raise ValueError(f"Hash mismatch (stored): {entry['file']}")
                raw = gzip.decompress(stored)
                if _sha256(raw) != entry["sha256_json"]:
                    raise ValueError(f"Hash mismatch (content): {entry['file']}")
                runners[entry["runner"]] = json.loads(raw)
            out[board] = runners
        return out

    def board_meta(self, board: str) -> dict:
        return self.manifest["boards"][board]

    # ------------------------------------------------------------------
    # Per-runner statistics
    # ------------------------------------------------------------------

    @cached_property
    def stats(self) -> dict[str, dict[str, RunnerStats]]:
        out: dict[str, dict[str, RunnerStats]] = {}
        for board, runners in self.boards.items():
            board_stats: dict[str, RunnerStats] = {}
            for runner, payload in runners.items():
                rows = payload["results"]
                s = RunnerStats(
                    runner=runner,
                    model=rows[0]["model"],
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
                    if isinstance(duration, int) and not isinstance(duration, bool):
                        s.durations_ms.append(duration)
                    s.input_tokens += r.get("input_tokens") or 0
                    s.output_tokens += r.get("output_tokens") or 0
                    s.cache_read_tokens += r.get("cache_read_tokens") or 0
                    s.cli_reported_cost += r.get("actual_cost_usd") or 0.0
                    metrics = r.get("metrics")
                    if metrics is None:
                        continue
                    s.artifacts += 1
                    if metrics.get("compile_pass") is True:
                        s.compile_passes += 1
                    if metrics.get("ci_pass") is True:
                        s.ci_passes += 1
                    if metrics.get("ungrounded_numeric_count") == 0:
                        s.zero_ungrounded += 1
                    score = metrics.get("generalist_review_score")
                    if isinstance(score, (int, float)):
                        s.review_scores.append(float(score))
                board_stats[runner] = s
            out[board] = board_stats
        return out

    def ranked(self, board: str) -> list[RunnerStats]:
        return sorted(
            self.stats[board].values(),
            key=lambda s: (-s.gate_passes, s.median_seconds),
        )

    def total_cost(self, board: str) -> float:
        return sum(s.cost for s in self.stats[board].values())

    # ------------------------------------------------------------------
    # Grids and cross-board views
    # ------------------------------------------------------------------

    def case_names(self, board: str = "v3") -> list[tuple[int, str]]:
        payload = next(iter(self.boards[board].values()))
        return [
            (r["eval_case"]["index"], r["eval_case"]["name"])
            for r in payload["results"]
        ]

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
    def ungrounded_artifacts_all_boards(self) -> int:
        """Artifacts (any board, any runner) with an ungrounded numeric."""
        count = 0
        for runners in self.boards.values():
            for payload in runners.values():
                for r in payload["results"]:
                    metrics = r.get("metrics")
                    if metrics is None:
                        continue
                    if metrics.get("ungrounded_numeric_count") != 0:
                        count += 1
        return count

    @cached_property
    def artifacts_all_boards(self) -> int:
        return sum(
            1
            for runners in self.boards.values()
            for payload in runners.values()
            for r in payload["results"]
            if r.get("metrics") is not None
        )

    # ------------------------------------------------------------------
    # The v2 fable truncation (board v2's harness defect, quantified)
    # ------------------------------------------------------------------

    @cached_property
    def v2_fable(self) -> dict:
        rows = self.boards["v2"]["fable"]["results"]
        killed = [
            r
            for r in rows
            if r.get("metrics") is None and r.get("success") is not True
        ]
        completed = [r for r in rows if r.get("metrics") is not None]
        return {
            "killed": len(killed),
            "completed": len(completed),
            "completed_passes": sum(1 for r in completed if gate_pass(r)),
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
    # Effort probe (frozen markdown record, parsed not retyped)
    # ------------------------------------------------------------------

    @cached_property
    def effort_probe(self) -> dict[str, list[dict]]:
        text = (SNAPSHOT_DIR / self.manifest["effort_probe"]["file"]).read_text()
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

    @cached_property
    def claude_probe_answer_sets(self) -> set[str]:
        """Distinct answers claude-opus-5 gave across every probe level."""
        return {
            a
            for row in self.effort_probe["claude"]
            for a in row["answers"]
        }

    # ------------------------------------------------------------------
    # Formatted fragments for inline prose
    # ------------------------------------------------------------------

    @staticmethod
    def money(x: float) -> str:
        return f"${x:.2f}"

    def encoder(self, board: str) -> str:
        meta = self.board_meta(board)
        return f"{meta['encoder_version']} ({meta['encoder_commit'][:8]})"

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

    @cached_property
    def case04_fails_v1_v2(self) -> int:
        """Model-runs that failed income_tax_rate_bands across v1 and v2."""
        count = 0
        for board in ("v1", "v2"):
            for payload in self.boards[board].values():
                (row,) = [
                    r
                    for r in payload["results"]
                    if r["eval_case"]["name"] == "income_tax_rate_bands"
                ]
                if not gate_pass(row):
                    count += 1
        return count

    @cached_property
    def case04_v3_passers(self) -> list[str]:
        passers = []
        for s in self.ranked("v3"):
            (row,) = [
                r
                for r in self.boards["v3"][s.runner]["results"]
                if r["eval_case"]["name"] == "income_tax_rate_bands"
            ]
            if gate_pass(row):
                passers.append(s.runner)
        return passers

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
        if problems:
            raise AssertionError(
                "Derived values disagree with the published board records:\n"
                + "\n".join(problems)
            )
        return (
            f"verified against published records: "
            f"{sum(len(e['gate']) for e in PUBLISHED.values())} gate counts, "
            f"medians, v3 artifacts/timeouts/costs"
        )


r = PaperResults()


if __name__ == "__main__":
    print(r.verify())
    for board in BOARD_ORDER:
        meta = r.board_meta(board)
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
    print(f"ungrounded artifacts, all boards: {r.ungrounded_artifacts_all_boards}")
    print(f"artifacts, all boards: {r.artifacts_all_boards}")
    print(f"v2 fable: {r.v2_fable}")
    print(f"v3 fable timeout: {r.v3_fable_timeout}")
    print(f"case 04 v1+v2 fails: {r.case04_fails_v1_v2}; v3 passers: {r.case04_v3_passers}")
    print(f"probe terra low: {r.probe_level('codex', 'low')}")
    print(f"probe terra xhigh: {r.probe_level('codex', 'xhigh')}")
    print(f"probe claude answers: {r.claude_probe_answer_sets}")

"""Fill the EncodeBench manuscript from frozen results — no kernel at render.

The paper's computation lives here, not in the manuscript. ``index.qmd.in``
is the template: prose plus ``{{name}}`` placeholders for every number,
``{{table:name}}`` blocks for every table, and ordinary markdown figures
pointing at PNGs this script writes. Running this module:

1. imports the frozen results object ``r`` and calls ``r.verify()`` first —
   a headline that disagrees with the published board records refuses the
   fill, exactly as it refused the render before;
2. runs the paper's derivations (``compute()``), which produce every scalar,
   every table as markdown text, and the figure PNG;
3. substitutes them into the template and writes ``index.qmd`` plus
   ``results/values.json`` (every scalar, sorted) so the filled numbers are
   inspectable without re-running anything.

Both directions fail loudly: a placeholder the pipeline did not fill, or a
value the template did not consume, is an error, so a stale template and a
stale pipeline are equally impossible to commit by accident.

    uv run --project paper python paper/fill_paper.py          # fill in place
    uv run --project paper python paper/fill_paper.py --check  # CI: regenerate
        into a temp dir and byte-compare against the committed outputs

Edit ``index.qmd.in`` and ``paper_results.py``; never ``index.qmd``.
"""

from __future__ import annotations

import argparse
import filecmp
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

PAPER = Path(__file__).resolve().parent
TEMPLATE = PAPER / "index.qmd.in"
FILLED = PAPER / "index.qmd"
VALUES = PAPER / "results" / "values.json"
FIGURES = PAPER / "figures"

sys.path.insert(0, str(PAPER))

PLACEHOLDER = re.compile(r"\{\{(table:)?([A-Za-z_][A-Za-z0-9_.\[\]'\"-]*)\}\}")

# Generated from the manuscript's inline `{python}` expressions; edit here,
# not by hand in index.qmd. Keys are placeholder names in index.qmd.in.
INLINE = {
    "n_models_word": "n_models_word",
    "n_v3_word": "n_v3_word",
    "n_shared_word": "n_shared_word",
    "v3_addendum": "v3_addendum",
    'r_corpus_release': 'r.corpus_release',
    'expr_lo': 'expr_lo',
    'expr_hi': 'expr_hi',
    'str_ra_lo': 'str(ra_lo)',
    'str_ra_hi': 'str(ra_hi)',
    'cov_others_lo_0f': 'f"{cov_others_lo:.0f}"',
    'cov_others_hi_0f': 'f"{cov_others_hi:.0f}"',
    'coverages_opus_5_1f': 'f"{coverages[\'opus-5\']:.1f}"',
    'review_lo': 'review_lo',
    'review_hi': 'review_hi',
    'str_review_cov_lo': 'str(review_cov_lo)',
    'str_review_cov_hi': 'str(review_cov_hi)',
    'luna_path': 'luna_path',
    'g553_gate_label': 'g553.gate_label',
    'sol3_gate_label': 'sol3.gate_label',
    'v3_luna_gate_label': 'v3["luna"].gate_label',
    'str_yard_min_gap': 'str(yard["min_gap"])',
    'str_yard_max_delta': 'str(yard["max_delta"])',
    'v3_opus_5_gate_label': 'v3["opus-5"].gate_label',
    'str_r_grounding_totals_v3_literals': 'str(r.grounding_totals_v3["literals"])',
    'str_r_grounding_totals_v3_artifacts': 'str(r.grounding_totals_v3["artifacts"])',
    'str_grounding_literals': 'str(grounding["literals"])',
    'str_grounding_artifacts': 'str(grounding["artifacts"])',
    'v3_codex_lo': 'v3_codex_lo',
    'v3_codex_hi': 'v3_codex_hi',
    'fable3_median_seconds': 'fable3.median_seconds',
    'fable_out_tokens': 'fable_out_tokens',
    'r_money_fable3_cost': 'r.money(fable3.cost)',
    'r_money_sol3_cost': 'r.money(sol3.cost)',
    'r_fable_cost_multiple_of_sol': 'r.fable_cost_multiple_of_sol',
    'r_encoder_version_v2': 'r.encoder_version("v2")',
    'r_run_date_v2': 'r.run_date("v2")',
    'r_encoder_version_v3': 'r.encoder_version("v3")',
    'r_run_date_v3': 'r.run_date("v3")',
    'delta_line': 'delta_line',
    'moved_word': 'moved_word',
    'delta_sum': 'delta_sum',
    'str_trans_fail_to_pass': 'str(trans["fail_to_pass"])',
    'str_trans_pass_to_fail': 'str(trans["pass_to_fail"])',
    'WORDS_trans_kill_to_pass': '_WORDS[trans["kill_to_pass"]]',
    'r_flip_binomial_p_2f': 'f"{r.flip_binomial_p:.2f}"',
    'WORDS_sum_r_runner_flips_gpt_5_5_values': '_WORDS[sum(r.runner_flips("gpt-5.5").values())]',
    'terra_path': 'terra_path',
    'sol_path': 'sol_path',
    'fable2_median_seconds': 'fable2.median_seconds',
    'v2_codex_lo': 'v2_codex_lo',
    'v2_codex_hi': 'v2_codex_hi',
    'str_v2f_killed': 'str(v2f["killed"])',
    'str_v2f_completed': 'str(v2f["completed"])',
    'str_v2f_completed_median_s': 'str(v2f["completed_median_s"])',
    'str_v2f_completed_passes': 'str(v2f["completed_passes"])',
    'timeout_policy_case_budget_s': 'f"{timeout_policy[\'case_budget_s\']:,}"',
    'timeout_policy_claude_wall_s': 'f"{timeout_policy[\'claude_wall_s\']:,}"',
    'str_timeout_policy_codex_short_wall_s': 'str(timeout_policy["codex_short_wall_s"])',
    'timeout_policy_codex_long_wall_s': 'f"{timeout_policy[\'codex_long_wall_s\']:,}"',
    'str_r_v3_codex_max_seconds': 'str(r.v3_codex_max_seconds)',
    'v3f_timeout_case': 'v3f_timeout["case"]',
    'v3f_timeout_seconds': 'f"{v3f_timeout[\'seconds\']:,}"',
    'str_probe_n_codex': 'str(probe_n_codex)',
    'str_probe_n_claude': 'str(probe_n_claude)',
    'r_thousands_probe_lo_median': 'r.thousands(probe_lo["median"])',
    'r_thousands_probe_xhigh_median': 'r.thousands(probe_xhigh["median"])',
    'str_probe_lo_wall_s': 'str(probe_lo["wall_s"])',
    'str_probe_xhigh_wall_s': 'str(probe_xhigh["wall_s"])',
    'r_thousands_probe_ultra_median': 'r.thousands(probe_ultra["median"])',
    'r_thousands_probe_high_median': 'r.thousands(probe_high["median"])',
    'str_probe_ultra_wall_s': 'str(probe_ultra["wall_s"])',
    'min_probe_ultra_all_0f_max_probe_ultra_all_0f': 'f"{min(probe_ultra[\'all\']):,.0f}–{max(probe_ultra[\'all\']):,.0f}"',
    'str_r_claude_probe_wall_range_0': 'str(r.claude_probe_wall_range[0])',
    'str_r_claude_probe_wall_range_1': 'str(r.claude_probe_wall_range[1])',
    'r_money3_claude_other_lo': 'r.money3(claude_other_lo)',
    'r_money3_claude_other_hi': 'r.money3(claude_other_hi)',
    'r_money3_claude_low_median': 'r.money3(claude_low_median)',
    'r_money3_r_claude_probe_low_samples_0': 'r.money3(r.claude_probe_low_samples[0])',
    'r_money3_r_claude_probe_low_samples_1': 'r.money3(r.claude_probe_low_samples[1])',
    'WORDS_case04_runs_v1_v2': '_WORDS[case04["runs_v1_v2"]]',
    'WORDS_case04_attempts_failed': '_WORDS[case04["attempts_failed"]]',
    'case04_passers': 'case04_passers',
    'disc_gate_passes_disc_cases': 'f"{disc[\'gate_passes\']}/{disc[\'cases\']}"',
    'WORDS_disc_limit_errors': '_WORDS[disc["limit_errors"]]',
    'disc_limit_median_s': 'f"{disc[\'limit_median_s\']}"',
    'str_opus2_dur_min_s': 'str(opus2_dur["min_s"])',
    'str_opus2_dur_max_s': 'str(opus2_dur["max_s"])',
    'str_r_v2_luna_review_coverage': 'str(r.v2_luna_review_coverage)',
    'str_r_fable_v1_cases': 'str(r.fable_v1["cases"])',
    'WORDS_r_fable_v1_kills_600s': '_WORDS[r.fable_v1["kills_600s"]]',
    'str_r_fable_v1_median_s': 'str(r.fable_v1["median_s"])',
    'str_r_fable_v1_gate_passes': 'str(r.fable_v1["gate_passes"])',
    'str_r_fable_v1_artifacts': 'str(r.fable_v1["artifacts"])',
    'VERIFIED': 'VERIFIED',
}


def compute() -> tuple[dict[str, str], dict[str, str]]:
    """Every derived value the manuscript uses, as strings.

    Returns ``(scalars, tables)``. The derivations are the manuscript's
    former setup and table cells, kept verbatim so the mapping from the
    live-kernel edition audits line by line.
    """

    from paper_results import BOARD_ORDER, r

    # Refuse to fill if any derived headline disagrees with the board records
    # posted to axiom-encode#1189 (URLs in the snapshot manifest).
    VERIFIED = r.verify()
    assert VERIFIED

    v1, v2, v3 = (r.stats[b] for b in BOARD_ORDER)
    ranked3 = r.ranked("v3")
    n_cases = len(r.case_names("v3"))
    assert n_cases == 16

    fable3 = v3["fable"]
    sol3 = v3["sol"]
    g553 = v3["gpt-5.5"]
    fable2 = v2["fable"]

    v2_codex = [s for s in v2.values() if s.backend == "codex"]
    v2_codex_lo = min(s.median_seconds for s in v2_codex)
    v2_codex_hi = max(s.median_seconds for s in v2_codex)
    v3_codex_lo = min(s.median_seconds for s in v3.values() if s.backend == "codex")
    v3_codex_hi = max(s.median_seconds for s in v3.values() if s.backend == "codex")

    review_scores = [s.mean_review_score for s in ranked3]
    review_lo = f"{min(review_scores):.1f}"
    review_hi = f"{max(review_scores):.1f}"
    review_cov_lo = min(s.review_score_count for s in ranked3)
    review_cov_hi = max(s.review_score_count for s in ranked3)

    deltas = r.v2_v3_deltas

    def _signed(d: int) -> str:
        return f"+{d}" if d > 0 else ("0" if d == 0 else f"-{abs(d)}")

    delta_line = ", ".join(
        f"{name} {_signed(d)}"
        for name, d in sorted(deltas.items(), key=lambda kv: -kv[1])
    )
    _WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
              7: "seven", 8: "eight", 9: "nine", 10: "ten"}
    moved_word = _WORDS[sum(1 for d in deltas.values() if d != 0)]
    delta_sum = _signed(sum(deltas.values()))
    trans = r.v2_v3_transitions
    yard = r.extremes_yardstick

    luna_path = ", ".join(str(r.gate_by_board["luna"][b]) for b in BOARD_ORDER)
    terra_path = ", ".join(str(r.gate_by_board["terra"][b]) for b in BOARD_ORDER)
    sol_path = ", ".join(str(r.gate_by_board["sol"][b]) for b in BOARD_ORDER)

    probe_lo = r.probe_level("codex", "low")
    probe_high = r.probe_level("codex", "high")
    probe_xhigh = r.probe_level("codex", "xhigh")
    probe_ultra = r.probe_level("codex", "ultra")
    probe_n_codex = r.probe_n("codex")
    probe_n_claude = r.probe_n("claude")
    assert len(r.claude_probe_answer_sets) == 1
    claude_low_median = r.claude_probe_cost_medians["low"]
    claude_other_lo = min(
        v for k, v in r.claude_probe_cost_medians.items() if k != "low"
    )
    claude_other_hi = max(
        v for k, v in r.claude_probe_cost_medians.items() if k != "low"
    )
    claude_low_all = r.probe_level("claude", "low")["all"]

    coverages = {s.runner: r.coverage_pct(s.runner) for s in ranked3}
    cov_others_lo = min(v for k, v in coverages.items() if k != "opus-5")
    cov_others_hi = max(v for k, v in coverages.items() if k != "opus-5")

    ra = r.repo_augmented_composition
    ra_lo = min(c["n_context_files"] for c in ra.values())
    ra_hi = max(c["n_context_files"] for c in ra.values())
    assert all(
        {"existing_target", "existing_target_test_context"} <= c["kinds"]
        for c in ra.values()
    )

    v2f = r.v2_fable
    v3f_timeout = r.v3_fable_timeout
    case04 = r.case04
    case04_passers = " and ".join(case04["v3_passers"])
    grounding = r.grounding_totals
    timeout_policy = r.v3_timeout_policy
    disc = r.discarded_opus5
    opus2_dur = r.v2_opus5_durations
    expr_lo = min(r.v3_expression_dates)
    expr_hi = max(r.v3_expression_dates)

    assert r.backends_used == {"codex", "claude"}

    fable_out_tokens = f"{fable3.output_tokens:,}"

    # Roster sizes derive: distinct models across boards, runners on v3, and
    # the runners the two full-roster boards share (the delta analysis).
    all_models = {
        s.model for board in BOARD_ORDER for s in r.stats[board].values()
    }
    n_models_word = _WORDS[len(all_models)]
    n_v3_word = _WORDS[len(ranked3)]
    n_shared_word = _WORDS[len(r.shared_runners)]

    # Runners folded into v3 after its record posted carry operator-recorded
    # environment facts (CLI versions the rows do not record); the paper
    # discloses them in one sentence per runner, or nothing.
    addendum_parts = []
    for entry in r.added_runners("v3"):
        st = v3[entry["runner"]]
        addendum_parts.append(
            f"{entry['runner']} (`{entry['model']}`) joined the v3 board on "
            f"{entry['added_after_record']}, after the board record posted: "
            "the rig re-materialized the same release object and ran the "
            "same encoder, engine, and RuleSpec commits, so the row folds "
            "under the contract, but the CLIs the harness does not record "
            f"had moved (codex {entry['codex_cli_version_at_launch']} and "
            f"Claude Code {entry['claude_cli_version_at_launch']} at launch, "
            "against the July board's 0.144 and 2.1.218) — a known "
            "unrecorded comparability input (@sec-parity). It scored "
            f"{st.gate_label} ({r.cold_gate_passes(entry['runner'])}/13 cold)."
        )
    v3_addendum = " ".join(addendum_parts)

    unpriced = r.unpriced_runners("v3")
    unpriced_caption = (
        " "
        + ", ".join(v3[u].model for u in unpriced)
        + " has no published per-token rate and the codex CLI reports no "
        "cost, so its cost cells stay blank rather than estimated."
    ) if unpriced else ""
    priced_only_caption = (
        " Suite costs cover the priced runners only." if unpriced else ""
    )

    def table(
        headers: list[str],
        rows: list[list[str]],
        caption: str = "",
        colwidths: list[int] | None = None,
    ) -> str:
        lines = [
            "| " + " | ".join(headers) + " |",
            "|" + "|".join("---" for _ in headers) + "|",
        ]
        lines += ["| " + " | ".join(row) + " |" for row in rows]
        if caption:
            attrs = (
                " {tbl-colwidths=\"[" + ",".join(map(str, colwidths)) + "]\"}"
                if colwidths
                else ""
            )
            lines += ["", f": {caption}{attrs}"]
        return "\n".join(lines)

    # --- the sixteen cases -------------------------------------------------
    ACT_DISPLAY = {
        ("statute", "ukpga", "1994", "23"): "Value Added Tax Act 1994",
        ("statute", "ukpga", "1992", "4"): "SSCBA 1992",
        ("statute", "ukpga", "2007", "3"): "Income Tax Act 2007",
        ("statute", "ukpga", "2003", "1"): "ITEPA 2003",
        ("statute", "ukpga", "2004", "12"): "Finance Act 2004",
        ("statute", "ukpga", "2012", "5"): "Welfare Reform Act 2012",
        ("statute", "ukpga", "2026", "11"): "Finance Act 2026",
        ("regulation", "uksi", "2006", "965"):
            "Child Benefit (Rates) Regulations 2006",
    }

    def provision_display(citation_path: str) -> str:
        _, kind, series, year, chapter, section = citation_path.split("/")
        unit = "reg." if kind == "regulation" else "s."
        return f"{ACT_DISPLAY[(kind, series, year, chapter)]} {unit} {section}"

    SUITE = [
        (1, "vat_standard_rate", "flat-rate control case", "parameters"),
        (2, "class_2_nic",
         "voluntary flat-rate contribution — see the labeling note below",
         "parameters"),
        (3, "class_1_secondary_nic",
         "employer-side rate and secondary threshold", "parameters"),
        (4, "income_tax_rate_bands",
         "basic, higher, and additional rate bands", "bands"),
        (5, "dividend_nil_rate", "band-conditional nil-rate amount", "bands"),
        (6, "personal_allowance_taper",
         "£100,000 half-excess taper with round-up", "tapers"),
        (7, "hicbc_phaseout",
         "charge liability above the £60,000 threshold — see the labeling "
         "note below", "tapers"),
        (8, "pension_annual_allowance",
         "annual allowance beside the s. 228ZA taper", "tapers"),
        (9, "marriage_allowance_transfer",
         "transferable allowance: elections, both-party conditions",
         "structure"),
        (10, "income_tax_liability_steps",
         "multi-step liability calculation; import-heavy", "structure"),
        (11, "uc_award_calculation",
         "universal credit: maximum amount minus reductions", "structure"),
        (12, "child_benefit_entitlement",
         "entitlement only — the rates live in a separate instrument",
         "grounding"),
        (13, "finance_act_2026_charge",
         "recency probe: a one-sentence charge for 2026–27", "grounding"),
        (14, "income_tax_main_rates",
         "the main-rate structure (the percentages live in annual finance "
         "acts)", "oracle path"),
        (15, "class_1_primary_nic",
         "employee-side Class 1 contributions", "oracle path"),
        (16, "child_benefit_weekly_rates",
         "the weekly rates case 12 must not invent", "oracle path"),
    ]

    assert [(i, n) for i, n, *_ in SUITE] == r.case_names("v3")
    citations = r.case_citations("v3")
    v3_modes = {
        row["eval_case"]["index"]: row["mode"]
        for row in r.boards["v3"]["sol"]["results"]
    }
    assert all(
        v3_modes[i] == ("repo-augmented" if group == "oracle path" else "cold")
        for i, _, _, group in SUITE
    )

    tables: dict[str, str] = {}

    tables["suite"] = table(
        ["#", "case", "provision", "probes", "group"],
        [
            [f"{i:02d}", f"`{name}`", provision_display(citations[i]), probes,
             group]
            for i, name, probes, group in SUITE
        ],
        "The sixteen cases. Cases 1–13 run cold; cases 14–16 run with "
        "repository context as oracle candidates. The provision column "
        "derives from the citation path frozen in every run row. SSCBA = "
        "Social Security Contributions and Benefits Act; ITEPA = Income Tax "
        "(Earnings and Pensions) Act.",
        colwidths=[5, 30, 24, 26, 15],
    )

    tables["boards"] = table(
        ["board", "run", "encoder", "runners", "suite cost"],
        [
            [
                b,
                r.run_date(b),
                f"`{r.board_meta(b)['encoder_version']}`",
                str(len(r.stats[b])),
                r.money(r.total_cost(b)),
            ]
            for b in BOARD_ORDER
        ],
        "The three boards. Costs are API-equivalents: codex-backend tokens "
        "priced at published July 2026 rates; Claude-backend costs are the "
        "CLI's own recorded per-call figures. All runs drew on "
        "subscription-billed seats." + priced_only_caption,
    )

    tables["v3"] = table(
        ["runner", "model", "gate pass", "cold", "T", "artifacts", "compile",
         "ci", "grounded", "median"],
        [
            [
                s.runner,
                f"`{s.model}`",
                f"**{s.gate_label}** ({s.gate_pct:.1f}%)",
                f"{r.cold_gate_passes(s.runner)}/13",
                str(s.timeouts) if s.timeouts else "—",
                f"{s.artifacts}/{s.cases}",
                s.compile_rate,
                s.ci_rate,
                s.grounded_rate,
                f"{s.median_seconds}s",
            ]
            for s in ranked3
        ],
        f"Board v3 — encoder {r.board_meta('v3')['encoder_version']}, run "
        f"{r.run_date('v3')}. The gate-pass column counts cases that clear "
        "all four gates; cold subsets the thirteen cold cases (the three "
        "oracle-path cases ran with the merged target encoding in-workspace, "
        "@sec-task). T counts cases that exhausted the recorded time budget; "
        "artifacts counts cases that produced a gradeable artifact; compile, "
        "ci (repository validation, companion tests included), and grounded "
        "rates cover produced artifacts only; median is case duration. "
        "OpenAI-family runners rode the codex path (workspace, tools) and "
        "Anthropic-family runners rode the Claude CLI prompt-only, so "
        "cross-family comparisons inherit @sec-parity. The advisory reviewer "
        "and oracle columns live in the board record.",
        colwidths=[9, 14, 15, 8, 5, 10, 10, 9, 10, 10],
    )

    grid_rows = r.grid("v3")
    runner_order = [s.runner for s in ranked3]
    tables["grid"] = table(
        ["case"] + runner_order,
        [
            [f"{row['index']:02d} `{row['name']}`"]
            + [row["cells"][runner] for runner in runner_order]
            for row in grid_rows
        ],
        "Board v3 per-case grid. P = gate pass, F = failed a gate (compile, "
        "validation, or grounding), T = timeout, E = no artifact. "
        "Cross-family column comparisons inherit @sec-parity.",
        colwidths=[100 - 9 * len(runner_order)] + [9] * len(runner_order),
    )

    tables["cost"] = table(
        ["runner", "input tok", "output tok", "cache read", "cost", "per pass",
         "basis"],
        [
            [
                s.runner,
                f"{s.input_tokens:,}",
                f"{s.output_tokens:,}",
                f"{s.cache_read_tokens:,}",
                r.money(s.cost) if s.cost is not None else "—",
                r.money(s.cost_per_pass) if s.cost_per_pass is not None else "—",
                s.cost_basis,
            ]
            for s in sorted(
                ranked3,
                key=lambda s: (s.cost is None, s.cost if s.cost is not None else 0.0),
            )
        ],
        "Board v3 cost annex, API-equivalent; rows ordered by suite cost, "
        "and per pass = cost per gate pass. Codex-backend rows price "
        "recorded tokens at published July 2026 rates, cache reads at 10% "
        "of the input rate. The Claude CLI reports its own per-call cost, "
        "recorded verbatim; recomputing it from a rate table would mean "
        "inventing a rate for claude-opus-5, which has no published price "
        "in the reference the harness bundles. The Claude CLI also reports "
        "near-zero input tokens in its non-interactive print mode, and we "
        "take its recorded cost as pricing the full exchange."
        + unpriced_caption,
        colwidths=[11, 15, 15, 15, 11, 13, 20],
    )

    _write_figure(r, BOARD_ORDER, ranked3)

    # Every inline expression the manuscript used, evaluated once here. The
    # keys are the placeholder names in index.qmd.in; the expressions are the
    # former `{python} ...` bodies, verbatim.
    ns = dict(locals())
    scalars: dict[str, str] = {}
    for name, expr in INLINE.items():
        scalars[name] = str(eval(expr, {"BOARD_ORDER": BOARD_ORDER, "r": r}, ns))
    return scalars, tables


def _write_figure(r, BOARD_ORDER, ranked3) -> None:
    """The boards figure, byte-stable across runs (no timestamps, fixed dpi)."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    matplotlib.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"],
        "figure.facecolor": "#faf9f6",
        "axes.facecolor": "#faf9f6",
        "text.color": "#1c1917",
        "axes.edgecolor": "#78716c",
        "axes.labelcolor": "#57534e",
        "xtick.color": "#57534e",
        "ytick.color": "#57534e",
    })

    INK = "#1c1917"
    RULE = "#e7e5e4"

    import math

    ncols = 3
    nrows = max(2, math.ceil(len(ranked3) / ncols))
    fig, axes = plt.subplots(
        nrows, ncols, figsize=(6.8, 1.8 * nrows), sharey=True, sharex=True
    )
    x_positions = {b: i for i, b in enumerate(BOARD_ORDER)}
    for ax in list(axes.flat)[len(ranked3):]:
        ax.set_visible(False)

    for ax, s in zip(axes.flat, ranked3):
        passes = r.gate_by_board[s.runner]
        xs = [x_positions[b] for b in BOARD_ORDER if b in passes]
        ys = [passes[b] for b in BOARD_ORDER if b in passes]
        truncated = s.runner == "fable"

        if truncated:
            ax.plot(xs, ys, color=INK, linewidth=1.6, linestyle=(0, (3, 2)),
                    zorder=2)
            ax.plot(xs[-1:], ys[-1:], marker="o", color=INK, markersize=6,
                    linestyle="none", zorder=3)
            ax.plot(xs[:1], ys[:1], marker="o", markerfacecolor="#faf9f6",
                    markeredgecolor=INK, markersize=6, linestyle="none",
                    zorder=3)
        else:
            ax.plot(xs, ys, marker="o", color=INK, linewidth=1.6,
                    markersize=5.5, zorder=2)

        for x, y in zip(xs, ys):
            ax.annotate(str(y), (x, y), textcoords="offset points",
                        xytext=(0, 7), ha="center", fontsize=8, color=INK)

        ax.set_title(s.runner, fontsize=9.5, fontfamily="monospace", pad=4)
        ax.set_ylim(0, 17.5)
        ax.set_xlim(-0.35, 2.35)
        ax.set_yticks([0, 4, 8, 12, 16])
        ax.set_xticks(list(x_positions.values()))
        ax.set_xticklabels(list(x_positions.keys()), fontsize=8)
        ax.tick_params(axis="both", labelsize=8, length=0)
        ax.grid(axis="y", color=RULE, linewidth=0.7)
        for spine in ("top", "right", "left"):
            ax.spines[spine].set_visible(False)
        ax.spines["bottom"].set_color(RULE)

    for row in axes:
        row[0].set_ylabel("gate passes", fontsize=8.5)
    fig.tight_layout(pad=0.8)
    FIGURES.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        FIGURES / "fig-boards.png",
        dpi=200,
        metadata={"Software": None},
    )
    plt.close(fig)


# ---------------------------------------------------------------------------
# Template filling
# ---------------------------------------------------------------------------

def fill(template: str, scalars: dict[str, str], tables: dict[str, str]) -> str:
    used: set[str] = set()

    def sub(m: re.Match) -> str:
        is_table, name = m.group(1), m.group(2)
        pool = tables if is_table else scalars
        if name not in pool:
            raise KeyError(f"placeholder {{{{{m.group(1) or ''}{name}}}}} has no value")
        used.add(("table:" if is_table else "") + name)
        return pool[name]

    out = PLACEHOLDER.sub(sub, template)
    leftover = re.findall(r"\{\{[^}]*\}\}", out)
    if leftover:
        raise SystemExit(f"unfilled placeholders remain: {leftover[:5]}")
    provided = set(scalars) | {"table:" + k for k in tables}
    unused = provided - used
    if unused:
        raise SystemExit(f"values computed but never used in the template: {sorted(unused)[:8]}")
    if "```{python}" in out or "`{python}" in out:
        raise SystemExit("filled manuscript still contains python cells")
    return out


def build(dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "results").mkdir(exist_ok=True)
    (dest / "figures").mkdir(exist_ok=True)
    global FIGURES
    FIGURES = dest / "figures"
    scalars, tables = compute()
    template = TEMPLATE.read_text(encoding="utf-8")
    filled = fill(template, scalars, tables)
    (dest / "index.qmd").write_text(filled, encoding="utf-8")
    (dest / "results" / "values.json").write_text(
        json.dumps(scalars, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def check() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        build(tmpdir)
        problems = []
        for rel in ["index.qmd", "results/values.json", *[
            "figures/" + p.name for p in (tmpdir / "figures").iterdir()
        ]]:
            a, b = tmpdir / rel, PAPER / rel
            if not b.exists() or not filecmp.cmp(a, b, shallow=False):
                problems.append(rel)
        if problems:
            print("committed outputs are stale — run fill_paper.py:", *problems, sep="\n  ")
            return 1
    print("filled manuscript, values, and figures match the pipeline")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="regenerate to a temp dir and byte-compare")
    args = ap.parse_args(argv)
    if args.check:
        return check()
    build(PAPER)
    print(f"wrote {FILLED.relative_to(PAPER.parent)}, results/values.json, figures/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

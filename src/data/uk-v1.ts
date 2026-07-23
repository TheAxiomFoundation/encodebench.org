// EncodeBench UK v1 — the suite as pinned in axiom-encode
// benchmarks/uk_model_capability_v1.yaml (PR #1191). Sixteen cases bound to
// the signed corpus release uk-rulespec-2026-07-14. This file mirrors the
// manifest for display; the manifest is the source of truth — update both
// together.

export const CORPUS_RELEASE = "uk-rulespec-2026-07-14";

export interface SuiteCase {
  index: number;
  name: string;
  provision: string;
  corpusPath: string;
  probes: string;
  mode: "cold" | "repo-augmented";
}

export interface SuiteStratum {
  title: string;
  blurb: string;
  cases: SuiteCase[];
}

export const STRATA: SuiteStratum[] = [
  {
    title: "Parameters and thresholds",
    blurb:
      "Flat rates and fixed amounts — the floor. A model that invents a rate here fails the grounding gate, not a reviewer's judgment.",
    cases: [
      {
        index: 1,
        name: "vat_standard_rate",
        provision: "Value Added Tax Act 1994 s. 2",
        corpusPath: "uk/statute/ukpga/1994/23/2",
        probes: "Flat-rate control case",
        mode: "cold",
      },
      {
        index: 2,
        name: "class_2_nic",
        provision: "Social Security Contributions and Benefits Act 1992 s. 13",
        corpusPath: "uk/statute/ukpga/1992/4/13",
        probes: "Weekly flat amount plus a small-profits threshold",
        mode: "cold",
      },
      {
        index: 3,
        name: "class_1_secondary_nic",
        provision: "Social Security Contributions and Benefits Act 1992 s. 9",
        corpusPath: "uk/statute/ukpga/1992/4/9",
        probes: "Employer-side rate and secondary threshold",
        mode: "cold",
      },
    ],
  },
  {
    title: "Bracket and band structure",
    blurb: "Rate tables and band-conditional amounts.",
    cases: [
      {
        index: 4,
        name: "income_tax_rate_bands",
        provision: "Income Tax Act 2007 s. 10",
        corpusPath: "uk/statute/ukpga/2007/3/10",
        probes: "Basic, higher, and additional rate bands",
        mode: "cold",
      },
      {
        index: 5,
        name: "dividend_nil_rate",
        provision: "Income Tax Act 2007 s. 13A",
        corpusPath: "uk/statute/ukpga/2007/3/13A",
        probes: "Band-conditional nil-rate amount",
        mode: "cold",
      },
    ],
  },
  {
    title: "Phaseouts and tapers",
    blurb: "Where encodings usually go wrong: interacting thresholds, withdrawal rates, and rounding directions.",
    cases: [
      {
        index: 6,
        name: "personal_allowance_taper",
        provision: "Income Tax Act 2007 s. 35",
        corpusPath: "uk/statute/ukpga/2007/3/35",
        probes: "£100,000 half-excess taper with round-up",
        mode: "cold",
      },
      {
        index: 7,
        name: "hicbc_phaseout",
        provision: "Income Tax (Earnings and Pensions) Act 2003 s. 681B",
        corpusPath: "uk/statute/ukpga/2003/1/681B",
        probes: "High income child benefit charge: £200 per £100 over the threshold",
        mode: "cold",
      },
      {
        index: 8,
        name: "pension_annual_allowance",
        provision: "Finance Act 2004 s. 228",
        corpusPath: "uk/statute/ukpga/2004/12/228",
        probes: "Annual allowance beside the s. 228ZA taper",
        mode: "cold",
      },
    ],
  },
  {
    title: "Cross-person and structural mechanics",
    blurb: "Elections, entity scoping, and multi-step formulas.",
    cases: [
      {
        index: 9,
        name: "marriage_allowance_transfer",
        provision: "Income Tax Act 2007 s. 55B",
        corpusPath: "uk/statute/ukpga/2007/3/55B",
        probes: "Transferable allowance: elections and both-party conditions",
        mode: "cold",
      },
      {
        index: 10,
        name: "income_tax_liability_steps",
        provision: "Income Tax Act 2007 s. 23",
        corpusPath: "uk/statute/ukpga/2007/3/23",
        probes: "The multi-step liability calculation; import-heavy",
        mode: "cold",
      },
      {
        index: 11,
        name: "uc_award_calculation",
        provision: "Welfare Reform Act 2012 s. 8",
        corpusPath: "uk/statute/ukpga/2012/5/8",
        probes: "Universal credit award: maximum amount minus income reductions",
        mode: "cold",
      },
    ],
  },
  {
    title: "Grounding discipline",
    blurb:
      "Cases built to catch invented numbers. One provision whose amounts live elsewhere; one act too new to be in any training set.",
    cases: [
      {
        index: 12,
        name: "child_benefit_entitlement",
        provision: "Social Security Contributions and Benefits Act 1992 s. 141",
        corpusPath: "uk/statute/ukpga/1992/4/141",
        probes:
          "Entitlement conditions only — the weekly rates live in the 2006 regulations, so any rate literal here is fabricated",
        mode: "cold",
      },
      {
        index: 13,
        name: "finance_act_2026_charge",
        provision: "2026 c. 11 s. 1",
        corpusPath: "uk/statute/ukpga/2026/11/1",
        probes:
          "Recency probe: the income tax charge for 2026–27, postdating model training data — the encoding must come from the supplied text",
        mode: "cold",
      },
    ],
  },
  {
    title: "Oracle candidates",
    blurb:
      "Provisions on the PolicyEngine UK comparison path. They run with repository context and will carry a live oracle check once that plumbing is verified; until then they grade on the same deterministic gates.",
    cases: [
      {
        index: 14,
        name: "income_tax_main_rates",
        provision: "Income Tax Act 2007 s. 6",
        corpusPath: "uk/statute/ukpga/2007/3/6",
        probes: "Main income tax rates on the worker oracle path",
        mode: "repo-augmented",
      },
      {
        index: 15,
        name: "class_1_primary_nic",
        provision: "Social Security Contributions and Benefits Act 1992 s. 8",
        corpusPath: "uk/statute/ukpga/1992/4/8",
        probes: "Employee-side Class 1 contributions on the worker oracle path",
        mode: "repo-augmented",
      },
      {
        index: 16,
        name: "child_benefit_weekly_rates",
        provision: "Child Benefit (General) Regulations 2006 reg. 2",
        corpusPath: "uk/regulation/uksi/2006/965/2",
        probes:
          "The enhanced and other weekly rates — the regulation the entitlement case must not invent",
        mode: "repo-augmented",
      },
    ],
  },
];

export interface Runner {
  name: string;
  model: string;
  family: string;
}

export const ROSTER: Runner[] = [
  { name: "terra", model: "gpt-5.6-terra", family: "OpenAI" },
  { name: "sol", model: "gpt-5.6-sol", family: "OpenAI" },
  { name: "gpt-5.5", model: "gpt-5.5", family: "OpenAI" },
  { name: "luna", model: "gpt-5.6-luna", family: "OpenAI" },
  { name: "fable", model: "claude-fable-5", family: "Anthropic" },
];

export const BOARD_COLUMNS = [
  { key: "gate", label: "gate pass", headline: true },
  { key: "compile", label: "compile", headline: false },
  { key: "ci", label: "ci", headline: false },
  { key: "grounded", label: "grounded", headline: false },
  { key: "coverage", label: "src coverage", headline: false },
  { key: "review", label: "review", headline: false },
  { key: "median", label: "median s", headline: false },
] as const;

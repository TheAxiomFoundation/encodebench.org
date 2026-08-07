import Image from "next/image";
import {
  BOARD,
  BOARD_ENCODER,
  BOARD_RUN,
  CORPUS_RELEASE,
  ROSTER,
  STRATA,
} from "@/data/uk-v1";

const GITHUB_ENCODE = "https://github.com/TheAxiomFoundation/axiom-encode";
const SUITE_PR = "https://github.com/TheAxiomFoundation/axiom-encode/pull/1191";

export default function Page() {
  return (
    <main>
      <Nav />
      <Hero />
      <Board />
      <GateBattery />
      <Suite />
      <Methodology />
      <SiteFooter />
    </main>
  );
}

function Nav() {
  return (
    <nav className="mx-auto flex max-w-5xl flex-wrap items-baseline justify-between gap-y-3 px-6 pt-8">
      <a href="#" className="text-lg font-semibold tracking-tight">
        Encode<span className="text-[var(--color-accent)]">Bench</span>
      </a>
      <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm sm:gap-x-6">
        <a className="link-quiet" href="#board">
          board
        </a>
        <a className="link-quiet" href="#how">
          how it works
        </a>
        <a className="link-quiet" href="#suite">
          suite
        </a>
        <a className="link-quiet" href="#methodology">
          methodology
        </a>
        <a className="link-quiet" href="/paper">
          paper
        </a>
        <a
          className="link-quiet"
          href={GITHUB_ENCODE}
          target="_blank"
          rel="noopener noreferrer"
        >
          GitHub
        </a>
      </div>
    </nav>
  );
}

function Hero() {
  return (
    <header className="mx-auto max-w-5xl px-6 pb-16 pt-20 sm:pt-28">
      <p className="mb-4 text-xs font-medium uppercase tracking-[0.18em] text-[var(--color-ink-muted)]">
        A benchmark from The Axiom Foundation
      </p>
      <h1 className="max-w-3xl text-4xl font-semibold leading-[1.1] tracking-tight sm:text-6xl">
        Can a model write the law as{" "}
        <span className="text-[var(--color-accent)]">code</span>?
      </h1>
      <p className="mt-6 max-w-2xl text-lg leading-relaxed text-[var(--color-ink-secondary)]">
        EncodeBench measures how well AI models turn statutes into cited,
        executable rules. Every score comes from deterministic gates: the
        encoding compiles, passes CI, and contains no number the source text
        doesn&rsquo;t.
      </p>
      <p
        className="mt-6 max-w-2xl text-lg italic text-[var(--color-ink-secondary)]"
        style={{ fontFamily: "var(--f-serif)" }}
      >
        Its sister benchmark,{" "}
        <a
          className="link-accent not-italic"
          style={{ fontFamily: "var(--f-body)" }}
          href="https://policybench.org"
          target="_blank"
          rel="noopener noreferrer"
        >
          PolicyBench
        </a>
        , asks whether a model can compute the law. EncodeBench asks whether it
        can write it.
      </p>
    </header>
  );
}

function Board() {
  return (
    <section id="board" className="mx-auto max-w-5xl px-6 pb-20">
      <div className="rounded-lg border border-[var(--color-rule)] bg-[var(--color-paper-elevated)] p-6 shadow-[0_1px_3px_rgba(28,25,23,0.06)] sm:p-8">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h2 className="text-2xl font-semibold tracking-tight">
            The board — UK v1
          </h2>
          <span className="rounded-full border border-[var(--color-rule-strong)] px-3 py-1 text-xs font-medium uppercase tracking-wide text-[var(--color-ink-secondary)]">
            Run {BOARD_RUN} · {BOARD_ENCODER}
          </span>
        </div>
        <p className="mt-3 max-w-2xl text-[0.95rem] text-[var(--color-ink-secondary)]">
          16 cases, six models, every run bound to the signed corpus release{" "}
          <span className="mono text-[0.85rem]">{CORPUS_RELEASE}</span>. Headline
          is the deterministic gate: the encode succeeds, the RuleSpec compiles,
          its companion tests pass, and no numeric literal is ungrounded.
        </p>
        <div className="mt-6 overflow-x-auto">
          <table className="bench-table min-w-[640px]">
            <thead>
              <tr>
                <th>runner</th>
                <th>model</th>
                <th className="text-[var(--color-accent)]">gate pass</th>
                <th>T</th>
                <th>artifacts</th>
                <th>compile</th>
                <th>ci</th>
                <th>grounded</th>
                <th>median</th>
              </tr>
            </thead>
            <tbody>
              {BOARD.map((row) => {
                const runner = ROSTER.find((r) => r.name === row.runner);
                return (
                  <tr key={row.runner}>
                    <td className="font-medium">{row.runner}</td>
                    <td className="mono text-[0.8rem] text-[var(--color-ink-secondary)]">
                      {runner?.model ?? row.runner}
                    </td>
                    <td className="font-semibold text-[var(--color-accent)]">
                      {row.gate}{" "}
                      <span className="mono text-[0.75rem] font-normal opacity-70">
                        {row.gatePct.toFixed(1)}%
                      </span>
                    </td>
                    <td className="mono text-[0.8rem]">
                      {row.timeouts === 0 ? "—" : row.timeouts}
                    </td>
                    <td className="mono text-[0.8rem]">{row.artifacts}/16</td>
                    <td className="mono text-[0.8rem]">{row.compile}</td>
                    <td className="mono text-[0.8rem]">{row.ci}</td>
                    <td className="mono text-[0.8rem]">{row.grounded}</td>
                    <td className="mono text-[0.8rem]">{row.median}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-5 text-sm text-[var(--color-ink-muted)]">
          Every number here came out of the run&rsquo;s recorded{" "}
          <span className="mono text-[0.8rem]">results.json</span> through the
          fold — none is hand-entered. A <span className="mono">T</span> is a
          case that hit the harness time ceiling, not a model that failed:
          those cases are held out of the compile and grounding denominators
          rather than counted as errors.
        </p>
        <p className="mt-3 rounded border border-[var(--color-rule-strong)] bg-[var(--color-paper)] p-4 text-sm text-[var(--color-ink-secondary)]">
          <strong className="font-semibold">
            This run is not reasoning-effort matched.
          </strong>{" "}
          The harness never set it. Its OpenAI path passes{" "}
          <span className="mono text-[0.8rem]">-c reasoning_effort</span>, which
          is not a recognized Codex config field — Codex accepts the flag and
          silently ignores it — and its Anthropic path passes no effort flag at
          all. Every runner therefore used its own CLI default, unset and
          unrecorded. A follow-up audit also found the backends did not sit the
          same exam: the Codex runners could read workspace files while the
          Anthropic runners ran prompt-only. Cross-family rows here should be
          read loosely. The next run fixes both — explicit recorded effort and
          an identical prompt-only exam for every backend. The{" "}
          <a className="link-accent" href="/paper">
            paper
          </a>{" "}
          carries the full account, every number derived from the frozen run
          artifacts.
        </p>
      </div>
    </section>
  );
}

const GATES = [
  {
    name: "encode",
    detail:
      "The model receives one provision's text, resolved from a signed corpus release, in a cold workspace: the resolved source text and its metadata, and no existing encoding of the target. It writes the RuleSpec module.",
  },
  {
    name: "compile",
    detail: "The module compiles in the Axiom rules engine.",
  },
  {
    name: "ci",
    detail:
      "Repository validation passes, including the companion tests every rule must carry.",
  },
  {
    name: "grounded",
    detail:
      "Zero ungrounded numeric literals: every number in the encoding appears in the source text. A model that recalls a rate instead of reading it fails here.",
  },
];

function GateBattery() {
  return (
    <section id="how" className="section-dark py-20">
      <div className="mx-auto max-w-5xl px-6">
        <h2 className="text-2xl font-semibold tracking-tight">
          Four gates, one headline
        </h2>
        <p className="mt-3 max-w-2xl text-[0.95rem] text-[var(--color-ink-secondary)]">
          A case passes for a model only when all four deterministic checks
          pass. The headline metric is the gate-pass rate and nothing else
          folds into it.
        </p>
        <ol className="mt-10 grid gap-6 sm:grid-cols-2">
          {GATES.map((gate, index) => (
            <li
              key={gate.name}
              className="rounded-lg border border-[var(--color-rule)] bg-[var(--color-paper-elevated)] p-5"
            >
              <div className="mono text-sm text-[var(--color-code-keyword)]">
                {index + 1} · {gate.name}
              </div>
              <p className="mt-2 text-[0.92rem] leading-relaxed text-[var(--color-ink-secondary)]">
                {gate.detail}
              </p>
            </li>
          ))}
        </ol>
        <p className="mt-8 max-w-2xl text-[0.95rem] text-[var(--color-ink-secondary)]">
          Reported alongside, never folded in: a statutory-fidelity review
          score, how many of the statute&rsquo;s numbers the encoding captured,
          a PolicyEngine oracle check where wired, latency, and cost.
        </p>
      </div>
    </section>
  );
}

function Suite() {
  return (
    <section id="suite" className="mx-auto max-w-5xl px-6 py-20">
      <h2 className="text-2xl font-semibold tracking-tight">
        The suite — 16 cases, stratified
      </h2>
      <p className="mt-3 max-w-2xl text-[0.95rem] text-[var(--color-ink-secondary)]">
        UK tax and benefit law, chosen to span the skills encoding demands.
        Every case resolves from the same signed release, so every model reads
        the same words.
      </p>
      <div className="mt-10 space-y-12">
        {STRATA.map((stratum) => (
          <div key={stratum.title}>
            <h3 className="text-lg font-semibold">{stratum.title}</h3>
            <p className="mt-1 max-w-2xl text-sm text-[var(--color-ink-muted)]">
              {stratum.blurb}
            </p>
            <div className="mt-4 overflow-x-auto">
              <table className="bench-table min-w-[560px]">
                <thead>
                  <tr>
                    <th className="w-10">#</th>
                    <th>provision</th>
                    <th>what it probes</th>
                    <th className="w-36">workspace</th>
                  </tr>
                </thead>
                <tbody>
                  {stratum.cases.map((suiteCase) => (
                    <tr key={suiteCase.name}>
                      <td className="mono text-[0.8rem] text-[var(--color-ink-muted)]">
                        {String(suiteCase.index).padStart(2, "0")}
                      </td>
                      <td>
                        <div className="font-medium">{suiteCase.provision}</div>
                        <div className="mono mt-0.5 text-[0.75rem] text-[var(--color-ink-muted)]">
                          {suiteCase.corpusPath}
                        </div>
                      </td>
                      <td className="text-[var(--color-ink-secondary)]">
                        {suiteCase.probes}
                      </td>
                      <td className="mono text-[0.8rem] text-[var(--color-ink-muted)]">
                        {suiteCase.mode}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

const METHODOLOGY = [
  {
    title: "Cold workspaces",
    detail:
      "With repository context, a model can lean on — or copy — the encoding that already exists for a provision, and scores drift as the repository grows. Capability cases run cold: the same source text and nothing else, identically for every model.",
  },
  {
    title: "Boards refuse to blend",
    detail:
      "Runs fold into one board only when the case set, the corpus release, and the score-affecting toolchain identity all match; checkout locations are ignored, everything else must be byte-identical. Add a model later without re-running the rest. Change a case, the release, or the encoder, and it's a new board — by construction, not convention.",
  },
  {
    title: "The reviewer never scores the headline",
    detail:
      "A pinned model reviews each encoding's statutory fidelity, identically for every contestant. It is one judge, it is noisy, and when its own family is on the board it is not a neutral party — so its score is reported next to the gates and never folded into them.",
  },
  {
    title: "A control model rides along",
    detail:
      "The roster includes a model that prior internal measurement found weak at this task. If the board can't separate it from the leaders, the instrument — not the models — is under suspicion.",
  },
  {
    title: "Every run carries its provenance",
    detail:
      "Each run binds the exact corpus release (Ed25519-verified), the encoder and rules-engine versions, and the repository and waiver state that graded it, with signed result evidence. A cell on the board traces to precisely what produced it.",
  },
];

function Methodology() {
  return (
    <section
      id="methodology"
      className="border-t border-[var(--color-rule)] bg-[var(--color-accent-light)] py-20"
    >
      <div className="mx-auto max-w-5xl px-6">
        <h2 className="text-2xl font-semibold tracking-tight">Methodology</h2>
        <dl className="mt-8 grid gap-8 sm:grid-cols-2">
          {METHODOLOGY.map((item) => (
            <div key={item.title}>
              <dt className="font-semibold">{item.title}</dt>
              <dd className="mt-1.5 text-[0.92rem] leading-relaxed text-[var(--color-ink-secondary)]">
                {item.detail}
              </dd>
            </div>
          ))}
        </dl>
        <p className="mt-10 max-w-2xl text-sm text-[var(--color-ink-muted)]">
          EncodeBench formalizes the internal encoder bake-off (July 2026) that
          routes The Axiom Foundation&rsquo;s own encoding pipeline. The suite,
          harness, and fold live in{" "}
          <a
            className="link-accent"
            href={GITHUB_ENCODE}
            target="_blank"
            rel="noopener noreferrer"
          >
            axiom-encode
          </a>{" "}
          (
          <a
            className="link-accent"
            href={SUITE_PR}
            target="_blank"
            rel="noopener noreferrer"
          >
            PR&nbsp;#1191
          </a>
          ).
        </p>
      </div>
    </section>
  );
}

function SiteFooter() {
  return (
    <footer className="border-t border-[var(--color-rule)] py-12">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-6 px-6">
        <a
          href="https://axiom.org"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-3"
        >
          <Image
            src="/logos/axiom-foundation.svg"
            alt="The Axiom Foundation"
            width={150}
            height={36}
          />
        </a>
        <p className="text-sm italic text-[var(--color-ink-muted)]">
          The world&rsquo;s rules, encoded.
        </p>
        <div className="flex gap-6 text-sm">
          <a
            className="link-quiet"
            href="https://policybench.org"
            target="_blank"
            rel="noopener noreferrer"
          >
            PolicyBench
          </a>
          <a
            className="link-quiet"
            href={GITHUB_ENCODE}
            target="_blank"
            rel="noopener noreferrer"
          >
            GitHub
          </a>
          <a className="link-quiet" href="mailto:hello@axiom-foundation.org">
            Contact
          </a>
        </div>
      </div>
    </footer>
  );
}

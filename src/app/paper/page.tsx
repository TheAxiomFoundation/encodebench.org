import type { Metadata } from "next";
import Image from "next/image";

const GITHUB_ENCODE = "https://github.com/TheAxiomFoundation/axiom-encode";
const GITHUB_SITE = "https://github.com/TheAxiomFoundation/encodebench.org";

export const metadata: Metadata = {
  title: "EncodeBench paper — measuring whether models can write law as code",
  description:
    "The EncodeBench paper: three toolchain-pinned boards of statute-to-RuleSpec encoding, the instrument defects the runs surfaced, and the pre-registered design that fixes them.",
};

const BIBTEX = `@misc{encodebench2026,
  author = {Ghenis, Max},
  title = {EncodeBench: Measuring whether language models can
           write law as code, and what it takes to measure
           that honestly},
  year = {2026},
  howpublished = {\\url{https://encodebench.org/paper}},
}`;

export default function PaperPage() {
  return (
    <main>
      <nav className="mx-auto flex max-w-5xl flex-wrap items-baseline justify-between gap-y-3 px-6 pt-8">
        <a href="/" className="text-lg font-semibold tracking-tight">
          Encode<span className="text-[var(--color-accent)]">Bench</span>
        </a>
        <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm sm:gap-x-6">
          <a className="link-quiet" href="/#board">
            board
          </a>
          <a className="link-quiet" href="/#suite">
            suite
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

      <header className="mx-auto max-w-5xl px-6 pb-12 pt-16 sm:pt-24">
        <p className="mb-4 text-xs font-medium uppercase tracking-[0.18em] text-[var(--color-ink-muted)]">
          Working paper · 2026-08-07
        </p>
        <h1 className="max-w-3xl text-4xl font-semibold leading-[1.1] tracking-tight sm:text-5xl">
          Measuring whether models can write law as{" "}
          <span className="text-[var(--color-accent)]">code</span> — and what
          it takes to measure that honestly
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-relaxed text-[var(--color-ink-secondary)]">
          Three toolchain-pinned boards of statute-to-RuleSpec encoding across
          six frontier models; the instrument defects the runs surfaced — a
          timeout that graded slowness as failure, an effort setting that did
          nothing, three backends administering different exams — and the
          pre-registered board that closes them. Every number derives in code
          from the frozen, signed run artifacts.
        </p>
        <div className="mt-8 flex flex-wrap gap-4">
          <a
            href="/paper/web/index.html"
            className="rounded-md bg-[var(--color-accent)] px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-[var(--color-accent-hover)]"
          >
            Read in the browser
          </a>
          <a
            href="/paper/encodebench.pdf"
            className="rounded-md border border-[var(--color-rule-strong)] px-5 py-2.5 text-sm font-medium text-[var(--color-ink)] transition-colors hover:border-[var(--color-accent)] hover:text-[var(--color-accent)]"
          >
            Download the PDF
          </a>
        </div>
      </header>

      <section className="mx-auto max-w-5xl px-6 pb-20">
        <div className="rounded-lg border border-[var(--color-rule)] bg-[var(--color-paper-elevated)] p-6 sm:p-8">
          <h2 className="text-lg font-semibold tracking-tight">Cite</h2>
          <pre className="mono mt-4 overflow-x-auto rounded border border-[var(--color-rule)] bg-[var(--color-paper)] p-4 text-[0.78rem] leading-relaxed text-[var(--color-ink-secondary)]">
            {BIBTEX}
          </pre>
          <p className="mt-5 text-sm text-[var(--color-ink-muted)]">
            The paper&rsquo;s source, frozen snapshot, and derivation module
            live in{" "}
            <a
              className="link-accent"
              href={`${GITHUB_SITE}/tree/main/paper`}
              target="_blank"
              rel="noopener noreferrer"
            >
              paper/
            </a>{" "}
            in this site&rsquo;s repository; the suite, harness, and board
            records live in{" "}
            <a
              className="link-accent"
              href={GITHUB_ENCODE}
              target="_blank"
              rel="noopener noreferrer"
            >
              axiom-encode
            </a>
            . Scores bind to the encoder that produced them, and the paper
            refreezes with every board.
          </p>
        </div>
      </section>

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
          </div>
        </div>
      </footer>
    </main>
  );
}

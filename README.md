# encodebench.org

Site for EncodeBench — The Axiom Foundation's benchmark for how well AI
models encode statutes into cited, executable rules.

Sister site to [policybench.org](https://policybench.org): PolicyBench asks
whether a model can compute the law; EncodeBench asks whether it can write
it as code.

The benchmark itself (suite manifest, harness, board fold) lives in
[axiom-encode](https://github.com/TheAxiomFoundation/axiom-encode) — see
`benchmarks/uk_model_capability_v1.yaml`, the `eval-suite` and `eval-board`
commands, and `docs/model-capability-eval.md`. This site displays it; the
harness is the source of truth. `src/data/uk-v1.ts` mirrors the suite
manifest and must be updated with it.

## Develop

```bash
bun install
bun run dev
```

## Design

Vendored Axiom Foundation design tokens (statute paper, legal ink, warm
amber) from `axiom-foundation.org/packages/ui` — sync `src/app/globals.css`
manually when the family tokens change. Logo assets are the canonical files
from the axiom-foundation.org repo.

## Deploy

Vercel, `axiom-foundation` scope, domain `encodebench.org`.

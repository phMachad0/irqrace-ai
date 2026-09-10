# research-ai-brain — wiki schema and operating manual

This vault is an LLM-maintained research wiki for a TCC (undergraduate thesis) on
**concurrency-defect detection in interrupt-driven embedded programs** — data races,
atomicity violations, and the static-analysis / model-checking tools that find them.

You (the LLM) write and maintain the `wiki/` layer, `index.md`, and `log.md`.
The human curates sources, asks questions, and directs the analysis.

## Why this vault exists

The literature is **background for a tool the human is building**. The goal is a static
analyzer that finds data races *and* atomicity violations in interrupt-driven embedded C with
**no false negatives** — over-approximate, accept false positives — and that emits a rich
per-candidate context record (call stacks, variables, slices, priority and masking state) so
an **LLM stage** can triage false positives, propose interrupt-specific fixes, apply them, and
re-verify. Detect → contextualize → triage → repair → re-verify.

**The vault holds two literatures.** The concurrency branch (interrupt-driven race and
atomicity-violation detection) and an **LLM-assisted static analysis** branch of seven sources
covering triage, specification inference and repair. All seven of the latter work on
*sequential* defects — the intersection with interrupt concurrency is empty, and that is where
this project sits. Map: `wiki/comparisons/LLM Integration Patterns.md`; the design that draws on
it: `wiki/LLM Stage Design.md`.

Consequences for how you should read and write here:

- **Recall outranks precision.** This corpus is precision-obsessed for historical reasons
  (`wiki/benchmarks/NASAC 2019 Prototype Competition.md`). When summarizing or recommending,
  say what a technique costs in *recall*, and treat any filter that drops a candidate without
  proving it impossible as a defect to flag.
- **Judge techniques by reimplementability**, not by headline numbers — three of the four
  tools are unobtainable, and one paper is an unreviewed preprint.
- **A solver may drop a candidate; the LLM may not.** A proof of impossibility licenses
  discarding; a model's judgement does not. Triage ranks, explains and buckets — the report
  keeps everything (`wiki/concepts/LLM Triage.md`).
- Full statement in `wiki/Thesis Goal.md`; build plan and stack in
  `wiki/comparisons/Reimplementation Assessment.md`; the static pipeline in
  `wiki/Pipeline Design.md`; the LLM stage in `wiki/LLM Stage Design.md`; recall hazards in
  `wiki/concepts/Soundness and False Negatives.md`. Read those before advising on direction.

## Layers

| Layer | Path | Who writes it | Rule |
| --- | --- | --- | --- |
| Raw sources | `Clippings/*.md`, `raw/*.pdf` | Human (Obsidian Web Clipper) or PDF extraction | **Immutable.** Never edit or reformat. Read-only source of truth. |
| Wiki | `wiki/**` | LLM only | Created, updated, cross-referenced on every ingest. |
| Navigation | `index.md`, `log.md` | LLM only | Updated on every ingest, query-that-was-filed, and lint pass. |
| Schema | `CLAUDE.md` (this file) | LLM + human together | Co-evolves as conventions change. |

**Tool artifacts and benchmarks live outside the vault**, one directory up: `../racebench`,
`../NIChecker`, `../BMC4AV` (full source — a CBMC fork). They are the primary evidence for
every count in `wiki/benchmarks/` and several in `wiki/comparisons/`. Check a claim against
them before repeating it from a paper; doing so has already resolved one contradiction and
explained another. Do not copy them into the vault and do not modify them.

`Clippings/` holds one markdown file per source, named after the tool or short title
(`SDRacer.md`, `IntRace.md`, `NIChecker.md`, `BMC4AV.md`). `raw/` holds the PDFs, and also
multi-file documentation sets kept as directories (`raw/racebench-deepwiki/`) — those stay
where the human put them rather than being flattened into `Clippings/`.
When a source arrives only as a PDF, extract it with `pdftotext` into `Clippings/`,
keep the frontmatter convention below, and note the extraction method in the frontmatter.

**Machine-generated documentation.** Some sources (DeepWiki exports, tool-generated docs) are
written *about* an artifact by an LLM rather than by its authors. Ingest them, but open the
source page with a provenance warning, separate what the source quotes with line references
from what it infers, and never let inferred content become a wiki claim without marking it.

## Directory layout of the wiki

```
wiki/
├── Overview.md                 map of content — the entry point
├── Synthesis.md                the evolving thesis: what the literature collectively says
├── Open Questions.md           gaps, unresolved conflicts, things to look up next
├── sources/    one page per paper       "X (paper).md"
├── concepts/   one page per idea        "Atomicity Violation.md"
├── tools/      one page per artifact    "X (tool).md" for tools we have papers for
├── benchmarks/ one page per benchmark suite
└── comparisons/ cross-cutting analyses that span several sources
```

**Paper vs. tool split.** A paper page describes *the publication* (claims, method,
evaluation, limitations). A tool page describes *the artifact* (what it does, what it is
built on, how every paper in the wiki reports on it — including papers that use it only
as a baseline). This split matters here because tools recur as competitors across papers:
NIChecker is the subject of one paper and a baseline in another.

## Page conventions

Every wiki page starts with YAML frontmatter (Dataview-queryable):

```yaml
---
type: source | concept | tool | benchmark | comparison | moc | project
tags: [wiki, <type>]
sources: ["[[SDRacer (paper)]]"]     # papers this page's claims come from
updated: YYYY-MM-DD
status: stub | draft | solid
---
```

Rules:

- **Filenames are human-readable Title Case with spaces** — links read as prose: `[[Atomicity Violation]]`.
- **Disambiguate against raw clippings.** `Clippings/SDRacer.md` is raw, so wiki pages use
  `SDRacer (paper)` and `SDRacer (tool)`. Never create a wiki page whose filename collides
  with a clipping — Obsidian's shortest-path links become ambiguous.
- **Every claim carries a source.** Attribute inline: "IntRace reports a 73.2% reduction in
  false positives relative to Rchecker ([[IntRace (paper)]], §4.2)". Numbers without a
  source do not belong in the wiki.
- **Link generously but only where real.** Aim for 5–15 outbound links per page. Do not
  invent a page name to link to; create the page or leave the term plain.
- **Preserve disagreement.** When two sources conflict, do not average them or silently
  prefer the newer one. State both, attribute both, and add the conflict to
  `wiki/comparisons/Contradictions.md`.
- **Distinguish claim from fact.** Write "BMC4AV reports…", not "BMC4AV is faster". Almost
  every performance number in this literature is self-reported, often on different hardware,
  sometimes copied from another paper. Say so.
- **English prose**, technical terms in the source vocabulary (ISR, happens-before, unwind
  bound). This vault is in English even though the thesis text may end up in Portuguese.
- **`type: project` pages state the human's direction, not a finding.** They are the one
  exception to "every claim carries a source": the objective itself is a directive and is
  labelled as such, while any claim *about the literature* on those pages still cites.

## Workflows

### Ingest

1. Read the new file in `Clippings/` end to end. For PDFs, extract to `Clippings/` first.
2. Discuss the key takeaways with the human before writing — what matters for the thesis,
   what to emphasize, what to skip.
3. Write `wiki/sources/<Name> (paper).md` using the source template below.
4. Create or update the artifact page in `wiki/tools/`.
5. Update every concept page the source touches. A source that introduces a new technique
   gets a new concept page; a source that merely uses one adds a line and a citation to the
   existing page.
6. Update `wiki/benchmarks/` with any benchmark the paper uses, including how *this* paper
   counted the defects in it (counts differ between papers — that is signal, not noise).
7. Update `wiki/comparisons/` — the capability matrix, the results table, and Contradictions
   if the new source disputes an earlier one.
8. Update `wiki/Synthesis.md` and `wiki/Open Questions.md` if the source moves the thesis.
9. Update `index.md` and append to `log.md`.

A single source typically touches 10–15 pages. That is expected.

### Query

1. Read `index.md` first, then drill into the pages it points at. Search `Clippings/` only
   when the wiki lacks the detail.
2. Answer with citations to wiki pages *and* the underlying source.
3. If the answer is durable — a comparison, a synthesis, a table the human will want again —
   ask whether to file it as a page under `wiki/comparisons/`, then log it. Good answers
   should compound in the wiki rather than vanish into chat history.

### Lint

Run when asked ("lint the wiki"). Check for:

- claims contradicted by a newer source that were never flagged;
- numbers repeated across pages that disagree with each other;
- orphan pages (no inbound links) and dead links (`[[X]]` with no `X.md`);
- concepts mentioned in three or more pages but lacking a page of their own;
- `status: stub` pages that a since-ingested source could now fill;
- gaps a targeted web search or a new paper would close.

Report findings as a list with suggested fixes; apply them only when told to.

## Log format

`log.md` is append-only, newest entries at the bottom, one `##` heading per entry:

```
## [YYYY-MM-DD] ingest | BMC4AV
## [YYYY-MM-DD] query | how do the four tools handle interrupt nesting
## [YYYY-MM-DD] lint | 3 dead links, 1 unflagged contradiction
## [YYYY-MM-DD] direction | project goal recorded
```

The consistent prefix keeps it greppable: `grep "^## \[" log.md | tail -5`.

## Source page template

```markdown
---
type: source
tags: [wiki, source]
sources: ["[[<Name> (paper)]]"]
updated: YYYY-MM-DD
status: draft
---

# <Full paper title>

**Venue / year · authors · clipping · PDF**

## Problem
## Approach
## Evaluation          (setup, benchmarks, headline numbers — with the caveats)
## Claims to trust and claims to check
## Limitations and threats to validity
## Relation to other sources in this wiki
```

## Conventions specific to this domain

- Report both **precision** (#TP/#WN) and **hit rate / recall** (#TP/#Vio) whenever a paper
  gives them. A tool with 100% precision and 39% hit rate is not a good tool, and papers
  that report only one of the two are making a choice worth noting.
- Always record the **ground-truth count** a paper assumes for a benchmark. Papers disagree
  about how many defects Racebench and the real-world suite actually contain, and most
  cross-paper comparisons quietly depend on that number.
- Record **which numbers were re-run and which were copied** from a prior paper, and on what
  hardware. Several comparisons in this literature mix the two.
- Note whether a tool is **open source and obtainable**. Multiple papers report failing to
  obtain baseline binaries — that shapes what any comparison can mean.

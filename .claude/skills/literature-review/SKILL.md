---
name: literature-review
visibility: public
category: authoring
description: Systematic literature review over academic databases via paper-search-mcp — search → triage → extract → cited synthesis. Two A2MC modes. PARAMETER-BOUNDS mode (the common one) — find published value ranges for a FATES/ELM parameter (e.g. "literature range for FATES Vcmax / fates_leaf_vcmax25top in arctic graminoids", "fine-root C:N for tundra shrubs") and produce a citation-backed bounds table that refines the lower/upper columns of a Phase-0 param list (FATES_Parameter_List_*.csv) / salib bounds — the evidence base for tightening a provisional range; checks curated trait databases (TRY, FRED, GRooT) as well as the paper literature for measured values. MANUSCRIPT mode — a topic review for a paper's introduction/discussion. Use when the user says "lit review on X", "what's the published range for parameter X", "find bounds for X from the literature", "check TRY/FRED for X", "review papers on X", "synthesize the literature for". NOT for a single-citation lookup. Pairs with markdown-to-pdf and manuscript-writing-style.
modes:
  requires_fates: false
  nutrient_pathway: any
  scope: [any]
  summary: "paper-search-mcp review → cited synthesis; PARAMETER-BOUNDS mode yields a citation-backed range table for a Phase-0 param list."
---

# Literature Review (A2MC)

A reproducible pipeline for a cited literature review using the `paper-search-mcp` MCP server.
Self-contained repo skill — depends only on the MCP tools + the repo's own `markdown-to-pdf`
skill (no user-level `~/.claude` skill, no Mac-specific tooling). Distilled from the P /
critical-minerals proposal review and adapted for A2MC's two uses.

## Two modes — pick first

- **PARAMETER-BOUNDS** (calibration): the goal is a **defensible numeric range** for one or
  more FATES/ELM parameters, to replace a provisional/default-anchored bound in a Phase-0 param
  list (`use_cases/<site>/parameters/FATES_Parameter_List_*.csv` — the `lower`/`upper` columns).
  Deliverable = a **bounds table**: `parameter | literature range [lo, hi] | central | units |
  PFT/context | citations`. This is the evidence layer behind those `lower`/`upper` bounds
  and the a2mc-init param-list "never invent a bound" rule.
- **MANUSCRIPT / TOPIC** (writing): a synthesis for a paper section or research plan.
  Deliverable = a themed markdown review separating established knowledge from hypotheses.

## Prerequisites

The `paper-search-mcp` server exposes tools as `mcp__paper-search-mcp__search_*` /
`..._read_*` / `..._download_*` (fetch their schemas with ToolSearch if not loaded). No install
needed inside this environment — the server is session-connected. PDF output uses the repo
`markdown-to-pdf` skill (pandoc + LaTeX on Perlmutter via `module load texlive`), NOT brew.
If the MCP tools are absent (e.g. a headless/cron run), say so and stop — this skill needs them.

## Stage 1 — Frame the question

- **Bounds mode:** list the exact parameters + their model meaning + units + the PFT/biome
  context (arctic graminoid? evergreen shrub?). Pull the parameter's mechanistic identity from
  the curated knowledge base / RAG first so the search terms are right (e.g. FATES
  `fates_leaf_vcmax25top` = *maximum carboxylation rate at 25 °C, top of canopy*, µmol CO2 m⁻² s⁻¹
  — search "Vcmax25 carboxylation rate arctic tundra <PFT>", not the bare parameter name).
- **Manuscript mode:** write 10–15 themes as a bullet list; confirm with the user before searching.

## Stage 2 — Search (parallel)

Fire **parallel** searches in one message: one call per (theme/param × source). Primary sources
`search_google_scholar`, `search_pubmed`, `search_semantic`; add `search_arxiv`/`search_biorxiv`
for pre-prints, `search_openalex`/`search_crossref` for breadth. Capture title, authors, year,
DOI, abstract per hit. **Never fabricate a paper** — every entry traces to a tool result.

### Curated trait & data databases — check these FIRST for parameter bounds

For parameter-bounds work, curated **trait databases** are often better than a paper-by-paper
search: they hold thousands of *measured* values in consistent, mappable units, filterable by
species / growth form / biome. Check the relevant ones alongside the paper search:

| Database | Covers (best for) → FATES param | Access | Cite as |
|---|---|---|---|
| **TRY** — [try-db.org](https://www.try-db.org/) | leaf & whole-plant traits: SLA (→ `fates_leaf_slatop`), leaf N/P (→ `fates_stoich_nitr`/`fates_stoich_phos`, leaf organ), Vcmax (→ `fates_leaf_vcmax25top`), leaf lifespan, wood density (→ `fates_wood_density`), seed mass | **data request** (register → request traits × species); returns measured records | the TRY dataset DOI + trait IDs + release version |
| **FRED** — [roots.ornl.gov](https://roots.ornl.gov/) (Fine-Root Ecology Database, ORNL DAAC) | fine-root traits: root N/P (→ `fates_stoich_nitr`/`fates_stoich_phos`, **fineroot** organ), SRL, tissue density, rooting depth, porosity. NOTE: FATES has **no** fine-root radius/diameter parameter — FRED radius/SRL inform root-chemistry & turnover context, not a direct calibration knob | **open download** (ORNL DAAC) | the FRED release DOI + version |
| **GRooT** — global root traits (curated FRED-derived) | harmonized root traits, species-standardized | open (R package / download) | the GRooT data-paper DOI |
| **AusTraits** | Australian plant traits (broad, tidy, versioned; less arctic coverage) | open download | the AusTraits release DOI |
| **BAAD** | biomass & allometry, woody (→ `fates_allom_*`) | open | data-paper DOI |
| **sPlot / BIEN** | vegetation-plot + occurrence-linked traits | request / open | dataset DOI |

Rules for database-sourced values: **(a)** cite the database *release* (name + version + its DOI),
not just "TRY", so the value is reproducible; **(b)** record the exact trait ID/name + the
species/growth-form/biome filter you applied (for Kougarok: arctic tundra graminoid / deciduous +
evergreen shrub); **(c)** convert to the FATES parameter's units like any other value (Stage 4/5 —
e.g. TRY SLA in m²·kg⁻¹-leaf → `fates_leaf_slatop` in m²·gC⁻¹ via the leaf C-fraction); **(d)**
`paper-search-mcp` does NOT query these databases — for request-based ones (TRY, sPlot) return the
request details + DOI for the user to fetch, and for open ones (FRED, GRooT, AusTraits) point at
the download or a machine-readable subset. The no-fabrication rule applies identically: a database
value must trace to a real, cited release.

## Stage 3 — Triage

Rank hits HIGH/MEDIUM/LOWER by relevance + evidence quality (primary measurement > review >
model-parameterization paper). For bounds: prioritize papers that **report measured values with
units + a site/PFT context**. Deduplicate by DOI.

## Stage 4 — Extract (the numbers)

For HIGH papers, read via `read_*_paper` (or the abstract if no full text) and extract:
- **Bounds mode:** the reported value(s), units, measurement method, PFT/species, site/biome,
  N/uncertainty. Note whether it's a measured value vs another model's assumed parameter.
- **Manuscript mode:** key quantitative findings + units, mechanisms, site context, stated limits.

Convert every value to the model parameter's units before tabulating (unit mismatches are the
main bounds error). Flag any value you had to convert.

## Stage 5 — Synthesize

- **Bounds mode — write a FULL literature review, not just a table.** For EACH parameter, a
  self-contained subsection that a domain reader can audit end-to-end:
  1. **Physical meaning & model definition** — what the parameter represents in the model, the
     internal variable it maps to, and its exact **units** (state them explicitly; this is where
     bounds go wrong).
  2. **What the literature measures** — the measurable quantity the parameter corresponds to,
     and **how the published measurement maps to the model parameter** (state the unit conversion
     explicitly, with the arithmetic, when the measured unit differs — e.g. SLA reported as
     m²·kg⁻¹-leaf → ÷ leaf C-fraction ≈ 0.47 to get m²·gC⁻¹).
  3. **Reported values (cited)** — a short table of the key measurements: value(s) as reported,
     units-as-reported, converted value, PFT/species, site/biome, and the citation.
  4. **Derived bound** — the `[lo, hi]` window you adopt, the central estimate, and a one-line
     rationale (why this window for the target PFT — not global extremes, not over-narrow; widen
     + say so if the literature is thin).
  Then update the param-list CSV `lower`/`upper` for that row, and record the provenance
  (`literature (<first-author year>)`) in the accompanying bounds `.md` — the FATES CSV has no
  `bound_source` column, so keep the citation trail in the bounds doc, not an invented column.
  End with a **References** section (Stage 6 citation rules).
- **Themed synthesis (manuscript mode):** "why it matters" → "what's established" (cited) →
  "what's hypothesized" (flagged) → "what our site can test" → references. Iterate 3–5 drafts.

### Citations — real, clickable, VALIDATED (hard requirement)

Every citation MUST be a **real paper with a resolvable DOI, rendered as a clickable link**:
`[First-Author Year](https://doi.org/10.XXXX/…)` — never a bare string, never a fabricated DOI.
**Validate each DOI before including it**: confirm it resolves to the cited paper via
`mcp__paper-search-mcp__get_crossref_paper_by_doi` (or a `WebFetch` of the `https://doi.org/…`
URL) and check the returned title/authors/year match your citation. Drop any DOI that does not
validate. In the review, add a **DOI-validation note** (e.g. "all DOIs verified via Crossref on
<date>") so the reader knows they were checked. A citation whose DOI you could not validate is
not usable — soften the claim or remove it. This is the cardinal rule (Stage 2/4): no fabrication.

## Stage 6 — Output

Write the review/table to a markdown file (bounds mode: alongside the param list, e.g.
`use_cases/<site>/parameters/bounds_literature_<date>.md`; manuscript mode: an `ana_log`).
Render to PDF with the `markdown-to-pdf` skill if a shareable doc is wanted. Every citation must
resolve to a real DOI from the search results.

## Self-checks

- Every paper + value traces to a tool result (no fabrication) — the cardinal rule.
- Units reconciled to the model parameter; conversions flagged.
- Bounds windows justified (measured range for the target PFT, not invented, not global extremes).
- Measured values distinguished from other-models' assumed parameters.
- Paywalled papers: return the DOI for the user to fetch institutionally; never bypass a paywall.

## Cross-references

- `use_cases/<site>/parameters/FATES_Parameter_List_*.csv` (`lower`/`upper` columns; docs/37
  explicit-column format) — the provisional (default-anchored) bounds this refines.
- a2mc-init param-list step ("never invent a bound; anchor to the knowledge base / literature").
- `markdown-to-pdf` (repo skill) for PDF output; `manuscript-writing-style` for manuscript prose.

## Changelog

- 2026-07-12 — Added the **curated trait & data database** table (TRY, FRED, GRooT, AusTraits, BAAD, sPlot/BIEN) as a primary bounds source before Stage 3, with access + reproducible-citation rules. Mapped each trait to its FATES parameter **verified against the api-43 base file** (SLA→`fates_leaf_slatop`, leaf/root N&P→`fates_stoich_nitr`/`fates_stoich_phos` via the organ dim, Vcmax→`fates_leaf_vcmax25top`, wood density→`fates_wood_density`) and flagged that FATES has **no** fine-root radius parameter (so FRED radius/SRL are context, not a direct knob) — the EcoSIM codes in the adapter-kit source (`SLA1`/`CNLF`/`RRAD1M`/`CNRT`) do not carry over. Ported from the adapter-kit version.
- 2026-07-12 — Ported to `main` from the `adapter-kit` branch; adapted the parameter-bounds references from EcoSIM (its reference_bounds dir, bounds generator and VCMX codes — all adapter-kit-side, named here without linking since they do not exist on this branch) to the FATES/main param-list CSV (`use_cases/<site>/parameters/FATES_Parameter_List_*.csv` `lower`/`upper` columns; `fates_leaf_vcmax25top` example). Adapter-kit itself distilled it from the user-level `literature-review` skill (Mac/proposal tooling removed).

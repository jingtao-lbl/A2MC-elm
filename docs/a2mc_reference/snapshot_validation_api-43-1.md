# Snapshot Validation: profile api-43-1

**Generated:** 2026-04-30T17:56:02+00:00
**Verdict:** Green  (5/5 fixtures pass)

## Fixtures

| Fixture | Description | Result | Failures |
|---|---|---|---|
| `kougarok_cnp_eca` | Default Kougarok run: FATES + PARTEH=2 + CNP + ECA + CENTURY | PASS | 0 |
| `parteh1_carbon_only` | Carbon-only PARTEH=1: vector filter blocks CNP theory chunks | PASS | 0 |
| `elm_only_bgc` | ELM-only run (use_fates=False): kb_source filter excludes FATES | PASS | 0 |
| `kougarok_with_fire` | Kougarok + spitfire=1: fire content reaches retrieval | PASS | 0 |
| `kougarok_nocomp` | Kougarok + use_fates_nocomp=True: ECA/RD off | PASS | 0 |

## Snapshot excerpts

### `kougarok_cnp_eca`  (`Default Kougarok run: FATES + PARTEH=2 + CNP + ECA + CENTURY`)

**Active mode block:**
```
## Active Run Configuration
- bgc_mode: fates, FATES: enabled (PARTEH=2, CNP allocation (nutrient cycling ON))
- Nutrient cycling: CNP
- Competition: ON (ECA pathway)
- Soil decomposition: century
```
**Targeted context:** (0 chars)

**RAG context:** (10204 chars)

### `parteh1_carbon_only`  (`Carbon-only PARTEH=1: vector filter blocks CNP theory chunks`)

**Active mode block:**
```
## Active Run Configuration
- bgc_mode: fates, FATES: enabled (PARTEH=1, carbon-only allocation) - CNP mechanisms (PID controller, nutrient uptake, stoichiometry) do NOT apply to this run
- Nutrient cycling: C
- Competition: ON (RD pathway)
```
**Targeted context:** (0 chars)

**RAG context:** (9372 chars)

### `elm_only_bgc`  (`ELM-only run (use_fates=False): kb_source filter excludes FATES`)

**Active mode block:**
```
## Active Run Configuration
- bgc_mode: bgc (FATES DISABLED; FATES parameters and mechanisms do NOT apply)
- Nutrient cycling: CNP
- Nutrient competition: ECA
- Soil decomposition: ctc
- Active modifiers: methane
```
**Targeted context:** (0 chars)

**RAG context:** (9868 chars)

### `kougarok_with_fire`  (`Kougarok + spitfire=1: fire content reaches retrieval`)

**Active mode block:**
```
## Active Run Configuration
- bgc_mode: fates, FATES: enabled (PARTEH=2, CNP allocation (nutrient cycling ON))
- Nutrient cycling: CNP
- Competition: ON (ECA pathway)
- Soil decomposition: century
- FATES features: spitfire=1
```
**Targeted context:** (0 chars)

**RAG context:** (9977 chars)

### `kougarok_nocomp`  (`Kougarok + use_fates_nocomp=True: ECA/RD off`)

**Active mode block:**
```
## Active Run Configuration
- bgc_mode: fates, FATES: enabled (PARTEH=2, CNP allocation (nutrient cycling ON))
- Nutrient cycling: CNP
- Competition: OFF (PFTs in separate patches; ECA/RD do NOT apply)
- Soil decomposition: century
```
**Targeted context:** (0 chars)

**RAG context:** (10204 chars)

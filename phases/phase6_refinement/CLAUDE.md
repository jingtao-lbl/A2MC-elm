# Phase 6: Refinement

**Purpose:** Evaluate experiment results, extract lessons, update knowledge
**Status:** AI reasoning phase (uses Claude API) + Memory update
**Inputs:** Experiment results, hypotheses, expected outcomes
**Outputs:** Lessons learned, parameter updates, convergence assessment

---

## What This Phase Does

1. Receive handoff from Phase 5 (experiment results)
2. Compare results to expected outcomes
3. Evaluate each hypothesis (confirmed/rejected/inconclusive)
4. Extract lessons learned (discoveries, parameter insights, failed approaches)
5. Update Adaptive Memory with new knowledge
6. Assess convergence and decide next steps
7. Generate refinement report

---

## Scripts in This Folder

| Script | Purpose |
|--------|---------|
| `evaluate_results.py` | Evaluate experiment results (compare to hypotheses / expected outcomes) |
| `plot_experiment_comparison.py` | Experiment comparison plot |

---

## Key Inputs

| Input | Source | Description |
|-------|--------|-------------|
| Testing report | Phase 5 | Experiment results, costs |
| Hypothesis report | Phase 4 | Expected outcomes |
| Baseline results | Phase 2 | Control case performance |

---

## Key Outputs

| Output | Location | Description |
|--------|----------|-------------|
| Hypothesis outcomes | Report | Confirmed/rejected/inconclusive |
| Lessons | `memory/extracted/` | YAML for knowledge processing |
| Memory updates | `memory/data/` | discoveries.json, parameters.json |
| Refinement report | `memory/phase_results/{session_id}/phase6_refinement/` | Full JSON |
| Convergence status | Report | Continue/converged/stalled |

---

## Shared Tools Used

```python
from tools.extract_lessons import LessonExtractor
from tools.extract_knowledge import KnowledgeExtractor
from memory import MemoryManager
```

---

## Hypothesis Evaluation

```yaml
hypothesis_outcomes:
  - id: "H1"
    statement: "Reducing pid_kp will reduce FROOT_PFT10 error by >20%"
    outcome: "partial"  # confirmed, rejected, partial, inconclusive
    expected: ">20% improvement"
    observed: "16.7% improvement"
    evidence: "Cost reduced from 0.342 to 0.285"

  - id: "H2"
    statement: "Increasing nitr_store_ratio will improve PFT#10 N status"
    outcome: "rejected"
    expected: "10-20% increase in LEAF_PFT10"
    observed: "5% decrease in LEAF_PFT10"
    evidence: "Unexpected interaction with phosphorus limitation"
```

---

## Lesson Extraction

```yaml
lessons:
  - type: "discovery"
    content: "PID Kp reduction helps but is not sufficient alone for PFT#10"
    confidence: 0.8
    evidence: "H1 partial success - 17% vs expected 20%"

  - type: "parameter_insight"
    parameter: "fates_cnp_pid_kp"
    content: "Optimal range for PFT#10 appears to be 0.25-0.35"
    confidence: 0.7

  - type: "failed_approach"
    content: "Increasing N storage ratio alone does not improve PFT#10"
    why_failed: "P limitation becomes binding constraint"
    confidence: 0.85
```

---

## Convergence Assessment

| Status | Criteria | Next Action |
|--------|----------|-------------|
| `converged` | All targets within tolerance | Phase 7 (Final) |
| `improving` | Cost decreased, hypotheses confirmed | Next iteration |
| `stalled` | Little improvement, most hypotheses rejected | Revise approach |
| `diverging` | Cost increased | Return to Phase 3 |

---

## Memory Update

```python
# Update memory with new knowledge
memory = MemoryManager("memory/data")

for lesson in lessons:
    if lesson.type == "discovery":
        memory.add_discovery(
            name=lesson.content[:50],
            description=lesson.content,
            mechanism=lesson.evidence,
            affects=[...],
            confidence=lesson.confidence
        )
    elif lesson.type == "failed_approach":
        memory.add_failed_approach(
            approach=lesson.content,
            experiment_id=exp_id,
            why_failed=lesson.why_failed,
            severity="high" if lesson.confidence > 0.8 else "medium"
        )
```

---

## Success Criteria

- [ ] All experiments evaluated against hypotheses
- [ ] Lessons extracted and categorized
- [ ] Memory updated with new knowledge
- [ ] Convergence status determined
- [ ] Refinement report generated with next steps

---

## Next Phase / Iteration

**If converged:** → Phase 7 (Final configuration)

**If improving:** → Next iteration (Phase 0 with refined bounds)

**If stalled/diverging:** → Return to Phase 3 with new diagnosis focus

---

## When AI Works in This Phase

**Focus on:**
- Honest evaluation of hypotheses (don't overstate success)
- Extracting generalizable lessons
- Updating Memory with useful knowledge
- Making clear convergence recommendations

**Do NOT:**
- Mark rejected hypotheses as "partial success"
- Skip updating Memory with failed approaches
- Ignore unexpected results
- Declare convergence prematurely

---

## Reasoning Template

**See:** `templates/reasoning/phase6_refinement_template.md`

The refinement reasoning should follow a structured approach:

1. **Experiment Results Summary** - Table with status (confirmed/partial/rejected)
2. **Detailed Experiment Analysis** - Expected vs actual with ASCII diagrams
3. **Parameter Category Analysis** - Group by allocation, nutrient, storage, mortality
4. **Mechanism-Based Synthesis** - What we learned before/after
5. **Critical Insights** - Numbered actionable findings
6. **Fundamental Constraints** - Hard limits discovered
7. **Knowledge Updates** - Discoveries, failed approaches, parameter insights
8. **Convergence Assessment** - Status with criteria breakdown
9. **Next Iteration Strategy** - Focus and priority experiments

### Key Patterns from Iteration #1

**Honest Evaluation:** Be explicit about partial success vs rejection:
- CONFIRMED: Actual meets or exceeds expected
- PARTIAL: Correct direction but insufficient magnitude
- REJECTED: Wrong direction or unexpected outcome

**Category Analysis:** Group parameters systematically:
- Allocation (PID, allocation ratios)
- Nutrient uptake (vmax, affinity constants)
- Storage (store ratios, targets)
- Mortality (starvation thresholds)
- Phenology (timing parameters)

**Discovery Recording:** Use memorable names:
```yaml
name: "Allocation Paradox"
mechanism: "vmax_p ↑ → stress ↓ → PID ↓ root → uptake ↓"
confidence: 0.95
```

---

## Knowledge Extraction Pipeline

```
Phase 5 results
    ↓
evaluate_experiments.py (compare to hypotheses)
    ↓
extract_lessons.py (JSON → YAML)
    ↓
extract_knowledge.py (YAML → memory/data/*.json)
    ↓
RAG/GraphRAG update (if new relationships discovered)
```

---

## Iteration Decision Tree

```
                    ┌─────────────────┐
                    │ Evaluate Results │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
     ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
     │  All targets │  │   Some      │  │  No/Little  │
     │  within tol  │  │ improvement │  │ improvement │
     └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
            │                │                │
     ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐
     │  CONVERGED   │  │  IMPROVING  │  │  STALLED    │
     │  → Phase 7   │  │  → Next iter│  │  → Phase 3  │
     └─────────────┘  └─────────────┘  └─────────────┘
```

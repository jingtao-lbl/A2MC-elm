# [Site Name] - A2MC Use Case

**Location:** [City/Region, Country]
**Coordinates:** [Lat, Lon]
**Ecosystem:** [e.g., Arctic tundra, Boreal forest, Temperate grassland]
**Status:** [Planning / Active / Complete]

---

## Overview

Brief description of the site and calibration goals.

---

## Target PFTs

| PFT Index | Name | Description |
|-----------|------|-------------|
| PFT#X | [Name] | [Description] |
| PFT#Y | [Name] | [Description] |

---

## Validation Targets

### Biomass Targets

| Variable | PFT | Observed (g C/m²) | Uncertainty | Source |
|----------|-----|-------------------|-------------|--------|
| Leaf | PFT#X | XX.X | ±20% | [Citation] |
| Fine Root | PFT#X | XX.X | ±20% | [Citation] |

### Ecosystem Targets

| Variable | Observed | Uncertainty | Source |
|----------|----------|-------------|--------|
| LAI (peak) | X.X | ±20% | [Citation] |
| GPP (annual) | XXX | ±20% | [Citation] |

---

## Data Sources

- **Biomass data:** [Source/Citation]
- **Climate forcing:** [Source]
- **Soil data:** [Source]

---

## Configuration

Key site-specific parameters:

```yaml
site:
  name: "[Site Name]"
  lat: XX.XX
  lon: XX.XX

pfts:
  - index: X
    name: "[PFT Name]"

morris:
  n_trajectories: 30
  n_params: 162
```

---

## Key Findings

Document discoveries and lessons learned during calibration.

### Discovery 1: [Name]

**Description:** ...

**Mechanism:** ...

**Affected parameters:** ...

---

## Files

| File | Description |
|------|-------------|
| `config.yaml` | Site configuration |
| `validation_targets.json` | Target values for calibration |

---

## References

- [Relevant publications]
- [Data sources]

# A2MC Use Cases

This folder contains site-specific case studies using the A2MC framework.

## Structure

Each use case should have its own folder:

```
use_cases/
├── README.md                 # This file
├── TEMPLATE/                 # Template for new case studies
│   └── README.md
├── Kougarok/                 # Kougarok, Alaska (NGEE-Arctic)
│   ├── README.md
│   ├── config.yaml
│   └── validation_targets.json
└── YourSite/                 # Add your site here
    └── ...
```

## Creating a New Use Case

1. Copy the `TEMPLATE/` folder to create your site folder
2. Edit `config.yaml` with your site-specific settings
3. Define your validation targets in `validation_targets.json`
4. Document your findings in `README.md`

## Existing Use Cases

| Site | Location | PFTs | Status |
|------|----------|------|--------|
| [Kougarok](Kougarok/) | Alaska, USA | Arctic shrubs & graminoids | Active development |

## Contributing

If you use A2MC for your site, consider contributing your use case back to the community (with appropriate data sharing permissions).

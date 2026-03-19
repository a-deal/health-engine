# Contributing to Health Engine

Issues and pull requests are welcome.

## Good first contributions

- **New protocols** — Add a structured health protocol to `protocols/`. Follow the YAML format of existing ones (sleep-foundation, cardio-baseline).
- **Wearable integrations** — Add a new data source in `engine/integrations/`. Garmin and Apple Health exist as examples.
- **Scoring improvements** — Better thresholds, additional NHANES stratification, new compound pattern detection.
- **Documentation** — Clarify methodology, add metric explainers, improve onboarding docs.

## Development setup

```bash
git clone https://github.com/a-deal/health-engine.git
cd health-engine
pip install -e ".[dev]"
```

## Running tests

```bash
python3 -m pytest tests/ -v   # 121 tests
```

All PRs should pass the existing test suite. New features should include tests.

## Code style

- Python 3.11+
- Keep it simple — no heavy abstractions
- Thresholds and rules go in `engine/insights/rules.yaml`, not hardcoded
- Never commit personal health data

## Questions?

Open an issue. Happy to help.

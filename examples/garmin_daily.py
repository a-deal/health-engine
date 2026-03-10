#!/usr/bin/env python3
"""Pull Garmin data and generate daily insights."""

import yaml
from engine.integrations.garmin import GarminClient
from engine.insights.engine import generate_insights

# Load config
with open("config.yaml") as f:
    config = yaml.safe_load(f)

# Pull fresh Garmin data
client = GarminClient.from_config(config)
garmin_data = client.pull_all()

# Generate insights from the pull
insights = generate_insights(garmin=garmin_data)

print(f"\n{'='*50}")
print(f"  Daily Health Insights ({len(insights)} total)")
print(f"{'='*50}\n")

for ins in insights:
    icon = {"critical": "!!", "warning": " !", "positive": " +", "neutral": " ~"}.get(ins.severity, "  ")
    print(f"  [{icon}] {ins.title}")
    print(f"      {ins.body}\n")

"""Condition-aware coaching: load modifiers and apply to alerts.

Reads condition_modifiers.yaml and the user's conditions from their
config.yaml. Enriches alerts with condition-specific coaching context.
"""

import yaml
from pathlib import Path
from typing import Optional


_MODIFIERS_PATH = Path(__file__).parent / "condition_modifiers.yaml"
_modifiers_cache: dict | None = None


def _load_modifiers() -> dict:
    """Load and cache condition modifiers. Resolves inheritance."""
    global _modifiers_cache
    if _modifiers_cache is not None:
        return _modifiers_cache

    if not _MODIFIERS_PATH.exists():
        _modifiers_cache = {}
        return _modifiers_cache

    with open(_MODIFIERS_PATH) as f:
        raw = yaml.safe_load(f) or {}

    # Resolve inheritance
    for key, config in raw.items():
        parent = config.get("inherits")
        if parent and parent in raw:
            # Merge parent into child (child overrides parent)
            merged = {}
            for section in ("alert_modifiers", "additional_primary_metrics",
                            "retest_cadence_override", "doctor_referral_triggers"):
                parent_val = raw[parent].get(section)
                child_val = config.get(section)
                if child_val is not None:
                    merged[section] = child_val
                elif parent_val is not None:
                    merged[section] = parent_val
            for k, v in merged.items():
                if k not in config:
                    config[k] = v

    _modifiers_cache = raw
    return _modifiers_cache


def get_user_conditions(config: dict) -> list[dict]:
    """Extract conditions from user config.

    Expected format in config.yaml:
        profile:
          conditions:
            - type: type_2_diabetes
              diagnosed: 2024-06
              status: managed
              medications: [metformin]
    """
    profile = config.get("profile", {})
    return profile.get("conditions", [])


def enrich_alerts_with_conditions(
    alerts: list[dict],
    user_conditions: list[dict],
) -> list[dict]:
    """Add condition-specific coaching context to alerts.

    For each alert, if any of the user's conditions has a modifier
    for that alert's metric, append the coaching_context to the alert.
    Also adds doctor_referral flag when appropriate.
    """
    if not user_conditions:
        return alerts

    modifiers = _load_modifiers()
    condition_types = [c.get("type", "") for c in user_conditions]

    for alert in alerts:
        metric = alert.get("metric", "")
        alert_type = alert.get("type", "")
        contexts = []

        for cond_type in condition_types:
            cond_config = modifiers.get(cond_type, {})
            alert_mods = cond_config.get("alert_modifiers", {})

            # Match on metric name or alert type
            mod = alert_mods.get(metric) or alert_mods.get(alert_type)
            if mod and mod.get("coaching_context"):
                contexts.append({
                    "condition": cond_config.get("display_name", cond_type),
                    "context": mod["coaching_context"],
                })

        if contexts:
            alert["condition_context"] = contexts

    return alerts


def get_condition_primary_metrics(user_conditions: list[dict]) -> set[str]:
    """Get additional primary metrics needed for the user's conditions."""
    modifiers = _load_modifiers()
    metrics = set()

    for cond in user_conditions:
        cond_type = cond.get("type", "")
        config = modifiers.get(cond_type, {})
        for m in config.get("additional_primary_metrics", []):
            metrics.add(m)

    return metrics


def get_condition_retest_overrides(user_conditions: list[dict]) -> dict[str, int]:
    """Get retest cadence overrides from user's conditions.

    Returns the most aggressive (shortest) cadence for each marker
    across all conditions.
    """
    modifiers = _load_modifiers()
    overrides = {}

    for cond in user_conditions:
        cond_type = cond.get("type", "")
        config = modifiers.get(cond_type, {})
        for marker, months in config.get("retest_cadence_override", {}).items():
            if marker not in overrides or months < overrides[marker]:
                overrides[marker] = months

    return overrides


def get_condition_doctor_triggers(user_conditions: list[dict]) -> list[str]:
    """Get all doctor referral trigger descriptions for the user's conditions."""
    modifiers = _load_modifiers()
    triggers = []

    for cond in user_conditions:
        cond_type = cond.get("type", "")
        config = modifiers.get(cond_type, {})
        display = config.get("display_name", cond_type)
        for trigger in config.get("doctor_referral_triggers", []):
            triggers.append(f"[{display}] {trigger}")

    return triggers

#!/usr/bin/env python3
"""
Coaching simulation framework for testing Milo's behavior.

Loads scenario YAML files, runs multi-turn conversations against the Anthropic API
using Milo's full system prompt, then scores each response with a fast grader model.

Usage:
    python3 simulate.py                      # Run all scenarios
    python3 simulate.py --scenario 01        # Run one scenario (prefix match)
    python3 simulate.py --refresh-workspace  # Re-fetch workspace files from Mac Mini
    python3 simulate.py --report             # Show latest report summary
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from glob import glob
from pathlib import Path

import yaml
from anthropic import Anthropic
from dotenv import load_dotenv

# Paths
SIMULATE_DIR = Path(__file__).parent.resolve()
WORKSPACE_DIR = SIMULATE_DIR / "workspace"
SCENARIOS_DIR = SIMULATE_DIR / "scenarios"
REPORTS_DIR = SIMULATE_DIR / "reports"

# Models
COACH_MODEL = "claude-sonnet-4-6"
GRADER_MODEL = "claude-haiku-4-5-20251001"

# Workspace files to fetch from Mac Mini
WORKSPACE_FILES = ["SOUL.md", "AGENTS.md", "TOOLS.md"]

# Grader system prompt
GRADER_SYSTEM = """\
You are a coaching quality grader. You evaluate AI health coach responses against specific rubric criteria.

You will receive:
- Scenario context (persona, health data, situation)
- The user message
- The coach's response
- A list of rubric items to evaluate

For each rubric item, return a JSON object with:
- "item": the rubric text
- "pass": 1 if the coach met this criterion, 0 if not
- "explanation": one sentence explaining your judgment

Return ONLY a JSON array of these objects. No other text.

Be strict. The rubric exists because these behaviors matter. A vague or partial pass is a fail.
If the coach partially addressed something but missed the core intent, score 0.

Example output:
[
  {"item": "Asked permission before sharing opinion", "pass": 1, "explanation": "Coach asked 'want me to share what I think?' before giving advice."},
  {"item": "Referenced actual data", "pass": 0, "explanation": "Coach said 'your numbers look good' without citing specific values."}
]"""


def load_api_key() -> str:
    """Load Anthropic API key from .env files."""
    for env_path in [
        SIMULATE_DIR.parent / ".env",
        Path.home() / "src" / "daily-brief" / ".env",
        Path.home() / "src" / "inbox-ai" / ".env",
    ]:
        if env_path.exists():
            load_dotenv(env_path)
            key = os.getenv("ANTHROPIC_API_KEY")
            if key:
                return key
    # Fall back to environment
    key = os.getenv("ANTHROPIC_API_KEY")
    if key:
        return key
    print("ERROR: No ANTHROPIC_API_KEY found. Check .env files.")
    sys.exit(1)


def refresh_workspace():
    """Fetch workspace files from Mac Mini via SSH."""
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    for filename in WORKSPACE_FILES:
        print(f"  Fetching {filename}...")
        try:
            result = subprocess.run(
                ["ssh", "mac-mini", f"cat ~/.openclaw/workspace/{filename}"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                (WORKSPACE_DIR / filename).write_text(result.stdout)
                print(f"    Saved ({len(result.stdout)} bytes)")
            else:
                print(f"    WARN: Empty or failed for {filename}")
                if result.stderr:
                    print(f"    stderr: {result.stderr.strip()}")
        except subprocess.TimeoutExpired:
            print(f"    WARN: SSH timeout for {filename}")
        except Exception as e:
            print(f"    WARN: {e}")


def load_system_prompt() -> str:
    """Load and combine workspace files into a system prompt."""
    parts = []
    for filename in WORKSPACE_FILES:
        path = WORKSPACE_DIR / filename
        if path.exists():
            parts.append(path.read_text())
        else:
            print(f"WARN: {path} not found. Run with --refresh-workspace first.")
    if not parts:
        print("ERROR: No workspace files found. Run: python3 simulate.py --refresh-workspace")
        sys.exit(1)
    return "\n\n---\n\n".join(parts)


def load_scenarios(filter_prefix: str = None) -> list[dict]:
    """Load scenario YAML files, optionally filtered by prefix."""
    files = sorted(SCENARIOS_DIR.glob("*.yaml"))
    if not files:
        print(f"ERROR: No scenario files in {SCENARIOS_DIR}")
        sys.exit(1)

    scenarios = []
    for f in files:
        if filter_prefix and not f.stem.startswith(filter_prefix):
            continue
        with open(f) as fh:
            scenario = yaml.safe_load(fh)
            scenario["_file"] = f.name
            scenarios.append(scenario)

    if not scenarios:
        print(f"ERROR: No scenarios matching prefix '{filter_prefix}'")
        sys.exit(1)
    return scenarios


def build_context_block(scenario: dict) -> str:
    """Build the persona/mock data context that gets injected into the conversation."""
    persona = scenario.get("persona", {})
    mock = scenario.get("mock_data", {})

    lines = [
        "[SIMULATION CONTEXT - This is injected for testing. Treat it as real user data.]",
        f"User: {persona.get('name', 'Unknown')} (user_id: {persona.get('user_id', 'sim-unknown')})",
        f"Background: {persona.get('context', 'No context provided')}",
    ]

    if mock:
        lines.append("\nCurrent data (from tools):")
        for key, value in mock.items():
            lines.append(f"  {key}: {value}")

    lines.append(
        "\n[END SIMULATION CONTEXT - Respond as Milo. Do NOT call any tools. "
        "Use the mock data above as if you had called checkin/score/etc. "
        "Do NOT reference the simulation context in your response.]"
    )
    return "\n".join(lines)


def run_scenario(client: Anthropic, system_prompt: str, scenario: dict) -> dict:
    """Run a single scenario: multi-turn conversation + grading."""
    name = scenario.get("name", scenario["_file"])
    turns = scenario.get("turns", [])
    context_block = build_context_block(scenario)

    print(f"\n{'='*60}")
    print(f"Scenario: {name}")
    print(f"{'='*60}")

    messages = []
    turn_results = []
    total_pass = 0
    total_items = 0

    for i, turn in enumerate(turns):
        user_msg = turn["user"]
        rubric = turn.get("rubric", [])

        # First turn includes context block
        if i == 0:
            full_user_msg = f"{context_block}\n\n{user_msg}"
        else:
            full_user_msg = user_msg

        messages.append({"role": "user", "content": full_user_msg})

        print(f"\n--- Turn {i+1} ---")
        print(f"User: {user_msg}")

        # Get coach response
        try:
            response = client.messages.create(
                model=COACH_MODEL,
                max_tokens=1024,
                system=system_prompt,
                messages=messages,
            )
            coach_reply = response.content[0].text
        except Exception as e:
            coach_reply = f"[ERROR: {e}]"
            print(f"  Coach error: {e}")

        messages.append({"role": "assistant", "content": coach_reply})
        print(f"Milo: {coach_reply[:200]}{'...' if len(coach_reply) > 200 else ''}")

        # Grade the response
        if rubric:
            scores = grade_response(
                client,
                scenario=scenario,
                user_msg=user_msg,
                coach_reply=coach_reply,
                rubric=rubric,
            )
            passed = sum(s["pass"] for s in scores)
            total = len(scores)
            total_pass += passed
            total_items += total
            print(f"  Score: {passed}/{total}")
            for s in scores:
                icon = "PASS" if s["pass"] else "FAIL"
                print(f"    [{icon}] {s['item']}: {s['explanation']}")
        else:
            scores = []

        turn_results.append({
            "turn": i + 1,
            "user": user_msg,
            "coach": coach_reply,
            "rubric_scores": scores,
            "passed": sum(s["pass"] for s in scores),
            "total": len(scores),
        })

    overall_pass = total_pass == total_items and total_items > 0
    print(f"\nOverall: {total_pass}/{total_items} {'PASS' if overall_pass else 'FAIL'}")

    return {
        "scenario": name,
        "file": scenario["_file"],
        "turns": turn_results,
        "total_pass": total_pass,
        "total_items": total_items,
        "overall": "pass" if overall_pass else "fail",
    }


def grade_response(
    client: Anthropic,
    scenario: dict,
    user_msg: str,
    coach_reply: str,
    rubric: list[str],
) -> list[dict]:
    """Use grader model to score a coach response against rubric items."""
    persona = scenario.get("persona", {})
    mock = scenario.get("mock_data", {})

    grader_prompt = f"""\
Scenario context:
- Persona: {persona.get('name', 'Unknown')}, {persona.get('context', '')}
- Mock data: {json.dumps(mock, indent=2) if mock else 'None'}

User message:
{user_msg}

Coach response:
{coach_reply}

Rubric items to evaluate:
{json.dumps(rubric, indent=2)}

Score each rubric item. Return ONLY a JSON array."""

    try:
        response = client.messages.create(
            model=GRADER_MODEL,
            max_tokens=1024,
            system=GRADER_SYSTEM,
            messages=[{"role": "user", "content": grader_prompt}],
        )
        raw = response.content[0].text.strip()
        # Handle potential markdown wrapping
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3]
        scores = json.loads(raw)
        return scores
    except json.JSONDecodeError as e:
        print(f"  WARN: Grader returned invalid JSON: {e}")
        print(f"  Raw: {raw[:300]}")
        return [{"item": r, "pass": 0, "explanation": "Grader parse error"} for r in rubric]
    except Exception as e:
        print(f"  WARN: Grader error: {e}")
        return [{"item": r, "pass": 0, "explanation": f"Grader error: {e}"} for r in rubric]


def save_report(results: list[dict]) -> Path:
    """Save results to a timestamped JSON report."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M")
    report_path = REPORTS_DIR / f"{timestamp}.json"

    report = {
        "timestamp": datetime.now().isoformat(),
        "coach_model": COACH_MODEL,
        "grader_model": GRADER_MODEL,
        "scenarios": results,
        "summary": {
            "total_scenarios": len(results),
            "passed": sum(1 for r in results if r["overall"] == "pass"),
            "failed": sum(1 for r in results if r["overall"] == "fail"),
            "total_rubric_items": sum(r["total_items"] for r in results),
            "total_rubric_passed": sum(r["total_pass"] for r in results),
        },
    }

    report_path.write_text(json.dumps(report, indent=2))
    print(f"\nReport saved: {report_path}")
    return report_path


def show_latest_report():
    """Display a summary of the most recent report."""
    reports = sorted(REPORTS_DIR.glob("*.json"))
    if not reports:
        print("No reports found.")
        return

    latest = reports[-1]
    report = json.loads(latest.read_text())

    print(f"\nLatest report: {latest.name}")
    print(f"Timestamp: {report['timestamp']}")
    print(f"Coach model: {report['coach_model']}")
    print(f"Grader model: {report['grader_model']}")
    print()

    summary = report["summary"]
    print(f"Scenarios: {summary['total_scenarios']} "
          f"({summary['passed']} passed, {summary['failed']} failed)")
    print(f"Rubric items: {summary['total_rubric_passed']}/{summary['total_rubric_items']}")
    print()

    for s in report["scenarios"]:
        icon = "PASS" if s["overall"] == "pass" else "FAIL"
        print(f"  [{icon}] {s['scenario']} ({s['total_pass']}/{s['total_items']})")
        for turn in s["turns"]:
            for score in turn.get("rubric_scores", []):
                si = "+" if score["pass"] else "-"
                print(f"         [{si}] {score['item']}")


def main():
    parser = argparse.ArgumentParser(description="Milo coaching simulation framework")
    parser.add_argument("--scenario", help="Run only scenarios matching this prefix (e.g., '01')")
    parser.add_argument("--refresh-workspace", action="store_true",
                        help="Re-fetch workspace files from Mac Mini")
    parser.add_argument("--report", action="store_true", help="Show latest report summary")
    args = parser.parse_args()

    if args.refresh_workspace:
        print("Refreshing workspace files from Mac Mini...")
        refresh_workspace()
        if not args.scenario and not args.report:
            return

    if args.report:
        show_latest_report()
        return

    # Load API key
    api_key = load_api_key()
    client = Anthropic(api_key=api_key)

    # Load system prompt
    system_prompt = load_system_prompt()
    print(f"System prompt loaded: {len(system_prompt)} chars from {len(WORKSPACE_FILES)} files")

    # Load scenarios
    scenarios = load_scenarios(args.scenario)
    print(f"Loaded {len(scenarios)} scenario(s)")

    # Run scenarios
    results = []
    for scenario in scenarios:
        result = run_scenario(client, system_prompt, scenario)
        results.append(result)

    # Save report
    report_path = save_report(results)

    # Final summary
    passed = sum(1 for r in results if r["overall"] == "pass")
    failed = sum(1 for r in results if r["overall"] == "fail")
    total_items = sum(r["total_items"] for r in results)
    total_pass = sum(r["total_pass"] for r in results)
    print(f"\n{'='*60}")
    print(f"FINAL: {passed}/{len(results)} scenarios passed, "
          f"{total_pass}/{total_items} rubric items passed")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

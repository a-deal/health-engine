#!/usr/bin/env python3
"""Check kasane.db for new persons and queue Milo outreach.

Runs every hour via OpenClaw cron. Detects persons created since last check
that don't have an active Milo session. Creates context.md and logs the
outreach for the agent to pick up.

Usage: python3 scripts/new_user_check.py [--dry-run]
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

DB_PATH = Path('/Users/andrew/src/health-engine/data/kasane.db')
USERS_YAML = Path('/Users/andrew/.openclaw/workspace/users.yaml')
STATE_FILE = Path('/Users/andrew/src/health-engine/data/new_user_state.json')
USER_DATA_DIR = Path('/Users/andrew/src/health-engine/data/users')
OUTREACH_LOG = Path('/Users/andrew/src/health-engine/data/outreach_queue.jsonl')

DRY_RUN = '--dry-run' in sys.argv


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {'last_check': '2026-01-01T00:00:00+00:00', 'seen_ids': []}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def load_users_yaml():
    if USERS_YAML.exists():
        with open(USERS_YAML) as f:
            data = yaml.safe_load(f)
        return data.get('users', {})
    return {}


def find_user_by_person_id(users, person_id):
    """Find a user entry that has a matching person_id or user_id."""
    for phone, info in users.items():
        if info.get('person_id') == person_id:
            return phone, info
    return None, None


def find_user_by_he_user_id(users, he_user_id):
    """Find a user entry by health_engine_user_id."""
    for phone, info in users.items():
        if info.get('user_id') == he_user_id:
            return phone, info
    return None, None


def get_preferred_channel(user_info):
    """Get the first available channel from the user's channel list."""
    channels = user_info.get('channels', [])
    if not channels:
        # Legacy format fallback
        ch = user_info.get('channel')
        target = user_info.get('channel_target')
        if ch and target:
            return ch, target
        return None, None
    first = channels[0]
    return first.get('type'), first.get('target')


def create_minimal_context(person_row, user_data_dir):
    """Create a minimal context.md for a new user if one doesn't exist."""
    context_path = user_data_dir / 'context.md'
    if context_path.exists():
        return  # warm handoff already written

    person_id, name, he_user_id, created_at = person_row
    content = f"""# {name}

## Basics
- Signed up: {created_at[:10]}
- Source: Kasane app
- Status: New user, awaiting first Milo outreach

## What We Know
- No health data yet. First sync just landed.
- No prior conversation context. Cold start.

## Next Steps
- Milo sends first message: introduce yourself, ask about their goal
- Follow standard onboarding flow (cluster menu, wearable, labs, history)
"""
    user_data_dir.mkdir(parents=True, exist_ok=True)
    context_path.write_text(content)
    print(f'  Created context.md for {name}')


def main():
    state = load_state()
    users = load_users_yaml()
    last_check = state['last_check']
    seen_ids = set(state.get('seen_ids', []))

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Find persons created after last check
    cursor.execute(
        'SELECT id, name, health_engine_user_id, created_at FROM person '
        'WHERE created_at > ? AND deleted_at IS NULL '
        'ORDER BY created_at',
        (last_check,)
    )
    new_persons = cursor.fetchall()
    conn.close()

    if not new_persons:
        print('No new persons since last check.')
        state['last_check'] = datetime.now(timezone.utc).isoformat()
        save_state(state)
        return

    print(f'Found {len(new_persons)} new person(s):')

    for person_row in new_persons:
        person_id, name, he_user_id, created_at = person_row

        if person_id in seen_ids:
            continue

        print(f'  New: {name} ({person_id})')

        # Try to find their channel info
        phone, user_info = find_user_by_person_id(users, person_id)
        if not user_info and he_user_id:
            phone, user_info = find_user_by_he_user_id(users, he_user_id)

        if not user_info:
            print(f'    No channel info in users.yaml. Skipping outreach (manual setup needed).')
            seen_ids.add(person_id)
            continue

        channel_type, channel_target = get_preferred_channel(user_info)
        if not channel_type or not channel_target or channel_target == 'TBD':
            print(f'    Channel not configured yet. Skipping outreach.')
            seen_ids.add(person_id)
            continue

        # Create minimal context if no warm handoff exists
        if he_user_id:
            user_dir = USER_DATA_DIR / he_user_id
        else:
            user_dir = USER_DATA_DIR / person_id
        create_minimal_context(person_row, user_dir)

        # Queue outreach
        outreach = {
            'ts': datetime.now(timezone.utc).isoformat(),
            'person_id': person_id,
            'name': name,
            'channel': channel_type,
            'target': channel_target,
            'user_id': user_info.get('user_id', ''),
            'status': 'queued',
        }

        if DRY_RUN:
            print(f'    [DRY RUN] Would queue outreach: {channel_type}:{channel_target}')
        else:
            OUTREACH_LOG.parent.mkdir(parents=True, exist_ok=True)
            with open(OUTREACH_LOG, 'a') as f:
                f.write(json.dumps(outreach) + '\n')
            print(f'    Queued outreach: {channel_type}:{channel_target}')

        seen_ids.add(person_id)

    state['last_check'] = datetime.now(timezone.utc).isoformat()
    state['seen_ids'] = list(seen_ids)
    save_state(state)
    print('Done.')


if __name__ == '__main__':
    main()

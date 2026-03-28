#!/usr/bin/env python3
"""Create a context.md for a new user from form signup data or warm handoff notes.

Usage:
  # From landing page form data:
  python3 scripts/create_user_context.py --name "Patrick" --phone "+14155551234" --channel imessage --source landing-page

  # Warm handoff with notes:
  python3 scripts/create_user_context.py --name "Manny" --phone "+19255426289" --channel imessage --source warm-handoff --notes "Andrew's barber. Garage gym, wife into fitness. High motivation. Interested in lifting program."
"""

import argparse
from datetime import datetime
from pathlib import Path

USER_DATA_DIR = Path('/Users/andrew/src/health-engine/data/users')


def create_context(name, user_id, channel, source, notes=None):
    user_dir = USER_DATA_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    context_path = user_dir / 'context.md'

    if context_path.exists():
        print(f'context.md already exists for {user_id}. Skipping.')
        return

    today = datetime.now().strftime('%Y-%m-%d')

    sections = [f'# {name}', '', '## Basics']
    sections.append(f'- Signed up: {today}')
    sections.append(f'- Source: {source}')
    sections.append(f'- Channel: {channel}')
    sections.append(f'- Status: New user, awaiting first Milo outreach')
    sections.append('')

    if notes:
        sections.append('## What We Know')
        sections.append(notes)
        sections.append('')
        sections.append('## Coaching Notes')
        sections.append('- Warm handoff from Andrew. Milo should reference the context above in the first message.')
        sections.append('- Do NOT start cold. Use what we know to make the first message personal.')
    else:
        sections.append('## What We Know')
        sections.append('- No prior conversation context. Cold start from form signup.')
        sections.append('')
        sections.append('## Coaching Notes')
        sections.append('- Standard onboarding flow: cluster menu, wearable, labs, history.')

    sections.append('')
    sections.append('## Next Steps')
    sections.append('- Milo sends first message: introduce yourself, ask about their goal')
    sections.append('- Follow standard onboarding flow')
    sections.append('')

    context_path.write_text('\n'.join(sections))
    print(f'Created: {context_path}')
    print(f'Content:\n{"\n".join(sections[:15])}...')


def main():
    parser = argparse.ArgumentParser(description='Create context.md for a new user')
    parser.add_argument('--name', required=True)
    parser.add_argument('--user-id', help='Health engine user_id (defaults to lowercase first name)')
    parser.add_argument('--channel', default='imessage')
    parser.add_argument('--source', default='landing-page')
    parser.add_argument('--notes', help='Warm handoff notes from Andrew')
    parser.add_argument('--phone', help='Phone number (for reference)')
    args = parser.parse_args()

    user_id = args.user_id or args.name.lower().split()[0]
    create_context(args.name, user_id, args.channel, args.source, args.notes)


if __name__ == '__main__':
    main()

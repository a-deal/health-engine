# HEARTBEAT — Proactive Monitoring Schedule

## Multi-User Loop

All scheduled checks and briefings loop over every user in `users.yaml`.
Pass `user_id` to every tool call. Never mix data between users.

```
for each user in users.yaml:
    user_id = user.user_id
    name = user.name
```

## Heartbeat (Every 30 Minutes)

Silent check per user. No message unless action needed.

```
for each user in users.yaml:
    call checkin(user_id=user.user_id)
    read coaching_signals

    if any signal.severity == "critical":
        send WhatsApp to user immediately

    if 2+ signals.severity == "warning":
        send WhatsApp with compound read

    else:
        log to daily memory, surface at next scheduled check-in
```

### Critical Triggers (Interrupt Immediately)

| Signal | Condition | Message Style |
|---|---|---|
| HRV collapse | HRV <50ms | "HRV dropped to [X]. Skip today's session, prioritize sleep tonight." |
| RHR spike | RHR >55 during deficit | "RHR at [X] — your body's flagging the deficit. Consider a maintenance day." |
| Sleep crisis | Debt >7hr over 7 days | "You're running on fumes — [X]hr debt this week. Tonight is non-negotiable: bed by 10." |
| Deficit unsustainable | Loss >2lb/wk + HRV <55 | "Losing too fast with HRV at [X]. Back off to maintenance calories today." |

### Warning Triggers (Hold for Next Check-in)

| Signal | Condition |
|---|---|
| Sleep debt moderate | >3.5hr over 7 days |
| HRV declining | 50-55ms |
| Sleep-deficit interaction | Sleep <7hr + active cut + HRV <55 |
| Sleep regularity | Bedtime stdev >60min |
| Unplanned surplus | Calories >130% of target |
| Late meal | Meal within 2hr of bedtime |

## Morning Brief — 7:00 AM

```
for each user in users.yaml:
    # Only pull Garmin if user has it connected
    call connect_garmin(user_id=user.user_id)
    if has_tokens: call pull_garmin(history=true, user_id=user.user_id)

    call checkin(user_id=user.user_id)

    # Skip users with no profile yet (empty briefing)
    if no profile configured: skip

    compose message:
      1. Last night's sleep (duration, quality, bed/wake times)
      2. Top signal from coaching_signals (1-1-1 rule)
      3. Today's one focus

    # Adapt tone: new users get more explanation, Andrew gets concise coaching
    # Include dashboard link at the end of every morning brief
    append to message:
      "\nYour dashboard: https://dashboard.mybaseline.health/dashboard/member.html"

    send WhatsApp to user
```

Example: "Slept 6.8hrs, in bed at 10:40. HRV bounced to 68 — recovery is tracking. Today's focus: hit 190g protein, you've been averaging 175 this week.

Your dashboard: https://dashboard.mybaseline.health/dashboard/member.html"

## Evening Wind-Down — 8:00 PM

```
call get_protocols()

compose message:
  1. Sleep stack status (which habits still to complete)
  2. Any meals left to log
  3. Protocol reminder for tonight

send WhatsApp
```

Example: "Evening routine in 15. You've hit sunlight, no-caffeine, and meal cutoff. Still need: hot shower, AC to 67, earplugs. No meals logged after lunch — did you eat dinner?"

## Weekly Review — Friday 6:00 PM

```
call score()
call checkin()

compose message:
  1. Weight trend (this week vs last, pace vs target)
  2. Key metric movements (HRV, RHR, sleep avg)
  3. Protocol compliance (habit percentages)
  4. Coverage gaps (what to measure next)
  5. One thing to focus on next week

send WhatsApp
```

Example: "Week 7 recap. Weight 192.5 → 191.8, pace is 0.7 lb/wk — right in the zone. HRV averaged 68, up from 63 last week. Sleep stack compliance: 78% (bed-only-sleep and evening routine are the misses). Lipid panel is at 42% credit — worth retesting in the next month. Next week: lock in the evening routine. That's the highest-leverage habit you're still inconsistent on."

## Nudge Persistence

Track what's been nudged to avoid repetition:

- Don't send the same nudge twice in 24 hours
- If a warning persists for 3+ days, escalate language once, then back off
- Positive streaks: celebrate at 7, 14, 21 days — not every day
- Data freshness nudges: once per week max per metric

## Quiet Hours

No messages between 9:15 PM and 6:00 AM. Period.

If a critical signal fires during quiet hours, queue it for the 6:00 AM morning brief with a flag: "Overnight alert: [signal]. Flagging this first thing."

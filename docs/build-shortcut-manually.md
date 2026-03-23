# Build "Baseline Health Sync" — iPhone

Open Shortcuts app, tap **+**, name it **Baseline Health Sync**.

Search for actions using the search bar at the bottom. You'll repeat the same pattern 8 times, then do sleep, then one final action.

---

## Pattern (repeat for each metric below)

For each metric in the table, add TWO actions:

1. **Find Health Samples**
   - Type: [see table]
   - Sort by: Start Date → Latest First
   - Limit: ON → 1

2. **Get Details of Health Sample**
   - Get: Value

Do this for each row:

| # | Type to select |
|---|---------------|
| 1 | Resting Heart Rate |
| 2 | Heart Rate Variability |
| 3 | Step Count |
| 4 | Weight |
| 5 | VO2 Max |
| 6 | Oxygen Saturation |
| 7 | Active Energy |
| 8 | Respiratory Rate |

That's 16 actions total (2 per metric).

---

## Sleep (3 actions)

17. **Find Health Samples**
    - Type: Sleep Analysis
    - Sort by: Start Date → Latest First
    - Limit: ON → 1

18. **Get Details of Health Sample**
    - Get: Start Date

19. **Get Details of Health Sample**
    - Get: End Date

---

## Send to server (2 actions)

20. **Text**
    - Type this URL, but insert the magic variables from each action above:

```
https://auth.mybaseline.health/api/ingest_health_snapshot?token=NZCT4pzvxC36OSaCztUYjq2_LAkqdC5_LmTFysa9VAY&resting_hr=[Value from #1]&hrv_sdnn=[Value from #2]&steps=[Value from #3]&weight_lbs=[Value from #4]&vo2_max=[Value from #5]&blood_oxygen=[Value from #6]&active_calories=[Value from #7]&respiratory_rate=[Value from #8]&sleep_start=[Start Date from sleep]&sleep_end=[End Date from sleep]
```

**How to insert magic variables:** Tap where you want the value, then tap the magic variable icon (wand) above the keyboard. Scroll up to find the "Value" output from the correct "Get Details" action. Each one will show which metric it came from.

21. **Get Contents of URL**
    - URL: select the Text from action 20
    - (Leave as GET, no other settings needed)

---

## Total: 21 actions

---

## After Building

1. Tap the play button ▶ to run it once (grants Health permissions — tap Allow for everything)
2. Tap **share icon** (bottom) → **Copy iCloud Link**
3. Send Andrew the link

## Set Up Daily Automation

1. Open Shortcuts → **Automation** tab
2. Tap **+** → **Time of Day** → set **7:00 AM** → **Daily**
3. Choose **Baseline Health Sync**
4. Turn OFF **Ask Before Running**
5. Done

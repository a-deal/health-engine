# LinkedIn Post #1: Open Sourcing health-engine

**Status:** Draft (pending Paul review)
**Target:** First standalone LinkedIn post. Follows Feb 27 Paul reply comment.

---

Been building a health scoring engine on the side for the past year. Started as a personal project during a cut. Ended up going deeper than I expected.

The thing that got me: I have 7 blood draws over 2 years. 200 biomarkers. And when I actually scored my health picture against CDC population data, I was only 42% covered. Nobody had ever scored my sleep regularity, fasting insulin trend, or blood pressure at home. My glucose looked normal on every single draw. The trend on my insulin told a different story.

Every health product I tried tells you what your numbers are. None of them tell you what you're missing. And the gap between those two things is where the real risk lives.

So I built the layer I couldn't find. 20 metrics scored against real NHANES percentiles. Labs, wearables, vitals, self-report. It tells you where you stand, what's missing, and what it costs to close each gap. Turns out going from 0% to 90% costs under $300 and about an hour. Most of the highest-leverage metrics don't require a blood draw.

Today I'm open sourcing it: github.com/a-deal/health-engine

The timing matters. I've been working with Paul Mederos, who's been building Kasane (kasanelife.com), a health coaching app grounded in the same belief: structured health data is what makes coaching personal, not generic advice. Our work kept converging on the same problem from different directions. Open sourcing the scoring layer felt right. This should be shared infrastructure, not locked inside one product.

The repo works out of the box with Claude Code. Clone it, point it at your data, say "how am I doing?" and it coaches you from your actual numbers. No dashboard to check. You just talk to it.

If you're building in health, or just want a clear read on where you stand, it's yours.

---

## Notes

- Links to README "Why This Exists" section (same language: "what you're missing", coverage score, NHANES)
- Paul/Kasane mention is genuine, not promotional. Names the convergence.
- CTA is soft. "It's yours."
- Reads naturally after the Feb 27 Paul reply (ecosystem framing).
- No em dashes, no heavy quotes, no emojis.

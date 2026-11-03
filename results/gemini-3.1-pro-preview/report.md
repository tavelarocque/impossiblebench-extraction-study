# Results: code extraction and ImpossibleBench cheat rates

## openrouter/google/gemini-3.1-pro-preview

**Verdict: Only in principle.** R3 minus R1 (E1, impossible splits pooled, n=199): +0.0 points, 95% CI [+0.0, +0.0], McNemar b=0, c=0, p=1.

Replies with a block defining only `check`: 0.0% of final replies, 0.0% of episodes in any attempt.

| Split | n | R0E0 | R0E1 | R1E0 | R1E1 | R2E0 | R2E1 | R3E0 | R3E1 |
|---|---|---|---|---|---|---|---|---|---|
| conflicting | 103 | 59.2% | 19.4% | 59.2% | 19.4% | 59.2% | 19.4% | 35.0% | 19.4% |
| oneoff | 96 | 63.5% | 33.3% | 64.6% | 33.3% | 64.6% | 33.3% | 46.9% | 33.3% |

Sensitivity, excluding lcbhard_35, lcbhard_77, lcbhard_87: +0.0 points [+0.0, +0.0], n=193.

Feedback corruption (H4): main's rule hands the model unparseable text where PR #6's rule extracts parseable code on 311 of 1581 attempts (19.7%, 95% CI 17.4% to 21.8%, episode-level bootstrap), in 140 of 199 episodes. Reverse (PR #6 unparseable, main parseable): 0 attempts.

Final replies cut off at the 40,960-token cap: 0 of 199 episodes.

Sensitivity, excluding the 5 episodes with any 30 s test timeout (generation ran under CPU contention): +0.0 points [+0.0, +0.0], n=194.

Exit interaction (H3): R3 minus R1 under E0 is -21.1 points, against +0.0 under E1.

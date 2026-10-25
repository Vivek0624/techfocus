# Metric definitions

Views, reach, impressions and accounts engaged are different things. Views = plays/displays (can repeat per
person); reach = unique accounts; accounts engaged = unique accounts that interacted. `impressions` is deprecated.

| metric | formula | denominator / notes |
| --- | --- | --- |
| net follower growth | followers(end) − followers(start) | needs a follower snapshot on both dates |
| % follower growth | net ÷ followers(start) × 100 | undefined if start = 0 |
| reach per post | Σ media reach ÷ count(media with reach) | posts in range only |
| engagement rate by reach | median over posts of (likes+comments+shares+saved) ÷ reach × 100 | post skipped if any part is missing |
| follows per 1k reach | Σ daily follows ÷ Σ daily account reach × 1000 | account-level; the API does not attribute follows to posts; unavailable <100 followers |
| outlier multiple | post views ÷ median views of the account's *other* posts | needs ≥3 other posts |
| required daily net growth | (target − current) ÷ days remaining (min 1) | |
| best posting window | median outlier multiple per IST window | needs ≥2 windows with ≥3 posts each, otherwise "run a test" |
| experiment result | medians per arm, lift %, two-sided permutation test on the median difference | "insufficient_data" below min samples; confidence medium only if p<0.05 and ≥5 per arm |

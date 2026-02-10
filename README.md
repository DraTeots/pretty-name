# 🔤 Pretty GitHub Username Finder

Find available, **pronounceable, good-looking** short GitHub usernames by combining phonotactic analysis with BigQuery's GH Archive dataset.

## The Problem

All obvious 3–4 letter GitHub usernames are taken... or are they? Many short accounts are inactive squatters. GitHub's API rate limits (5,000/hr) make brute-force checking of 450K+ 4-letter combinations impractical. This toolkit solves the problem with a three-stage pipeline:

```
Generate pretty names → Filter against known taken → Verify survivors
   (local, instant)     (BigQuery, ~24 GB scan)     (GitHub endpoint)
      22K names              → ~few hundred            → winners
```

## Pipeline Overview

### Stage 1: Generate Pretty Names (`pretty_names.py`)

Not all 4-letter strings are created equal. `hero` is a great username; `xzqf` is not. This script scores all 456,976 lowercase 4-letter combinations (a–z) for human readability using six weighted criteria:

| Criterion | Weight | What it measures |
|---|---|---|
| Syllable structure | 0–25 pts | CVCV patterns ("luna") beat CCCC ("strm") |
| English bigram frequency | 0–30 pts | Common letter pairs ("th", "er", "in") score higher |
| Consonant cluster legality | 0–15 pts | "br", "st" are natural; "xz", "qw" are not |
| Vowel balance | 0–10 pts | 2 vowels in 4 letters is ideal |
| Letter pleasantness | 0–8 pts | q, x, z penalized |
| Ending quality | 0–5 pts | Ending in vowels or soft consonants (n, r, s, l) preferred |

Additional penalties apply for triple consonants/vowels, adjacent duplicate characters, and harsh letter combinations.

**At threshold 65, this produces ~22,300 candidates** (4.9% of all combinations) — names that a human would find easy to read, remember, and type.

```bash
# Generate all pretty names as CSV
python3 pretty_names.py --threshold 65 --format csv -o pretty_names.csv

# Only the crème de la crème
python3 pretty_names.py --threshold 80 --format csv -o elite_names.csv

# Filter by syllable pattern (CVCV = consonant-vowel-consonant-vowel)
python3 pretty_names.py --threshold 70 --pattern CVCV --show-scores

# Just stats, no file output
python3 pretty_names.py --threshold 60 --stats-only
```

Example output at score ≥ 90:

```
hero  96  CVCV       care  96  CVCV       fate  96  CVCV
core  96  CVCV       mare  96  CVCV       gate  96  CVCV
bore  96  CVCV       more  96  CVCV       rare  96  CVCV
date  96  CVCV       fore  96  CVCV       here  96  CVCV
```

### Stage 2: Filter Against Known Taken Usernames (BigQuery)

GH Archive records every public GitHub event since 2011. Every push, star, issue, PR, and comment includes the `actor.login` (username). By querying this dataset, we get a near-comprehensive list of **actively used** short usernames — far more efficient than hitting the GitHub API 450K times.

#### Setup (free, 5 minutes)

1. Go to [console.cloud.google.com/bigquery](https://console.cloud.google.com/bigquery)
2. Sign in with any Google account
3. Create a project (any name) — the BigQuery sandbox gives **1 TB/month free**
4. Open the SQL editor and run:

```sql
SELECT DISTINCT actor.login
FROM `githubarchive.year.2024`
WHERE LENGTH(actor.login) <= 4
  AND REGEXP_CONTAINS(actor.login, r'^[a-zA-Z0-9\-]+$')
ORDER BY actor.login;
```

5. Click **Save Results → CSV (local file)** to download

**Cost:** ~24 GB scanned per year-table query (2.4% of your free monthly quota).

> **Tip:** You don't need a billing account. The sandbox tier is sufficient. The `githubarchive` dataset is a public dataset — no connection setup needed, just reference it by name in SQL.

#### Advanced: Find gaps directly in BigQuery

```sql
-- Generate all 3-letter combos and find which ones have NO known user
WITH all_combos AS (
  SELECT combo FROM
    UNNEST(GENERATE_ARRAY(0, 46655)) AS i,
    UNNEST([
      CONCAT(
        SUBSTR('abcdefghijklmnopqrstuvwxyz0123456789',
               CAST(FLOOR(i / 1296) AS INT64) + 1, 1),
        SUBSTR('abcdefghijklmnopqrstuvwxyz0123456789',
               MOD(CAST(FLOOR(i / 36) AS INT64), 36) + 1, 1),
        SUBSTR('abcdefghijklmnopqrstuvwxyz0123456789',
               MOD(i, 36) + 1, 1)
      )
    ]) AS combo
),
known_users AS (
  SELECT DISTINCT LOWER(actor.login) AS login
  FROM `githubarchive.year.2024`
  WHERE LENGTH(actor.login) = 3
)
SELECT combo AS potentially_available
FROM all_combos
LEFT JOIN known_users ON all_combos.combo = known_users.login
WHERE known_users.login IS NULL
ORDER BY combo;
```

### Stage 3: Cross-Reference (`find_available.py`)

Combine the pretty name list with the BigQuery export to find names that are both **pretty AND potentially available**:

```bash
python3 find_available.py \
  --taken bigquery_export.csv \
  --pretty pretty_names.csv \
  --min-score 75 \
  -o candidates.csv
```

Output is sorted by prettiness score, highest first.

### Stage 4: Verify Candidates

The BigQuery approach has a blind spot: accounts that exist but have **never performed any public action** won't appear in GH Archive. So the candidate list will contain some false positives.

For final verification, use the GitHub registration endpoint (not the API — it gives false positives for reserved names). The best existing tool for this is [ui-1/nlet](https://github.com/ui-1/nlet), which emulates the signup form's username check.

Alternatively, a minimal verification script:

```python
import requests, time

session = requests.Session()
# Log into GitHub first, then grab your session cookie
session.cookies.set("user_session", "YOUR_SESSION_COOKIE")

with open("candidates.csv") as f:
    next(f)  # skip header
    for line in f:
        name = line.split(",")[0]
        r = session.post(
            "https://github.com/account/rename_check",
            data={"suggest_usernames": "true", "login": name},
            headers={"X-Requested-With": "XMLHttpRequest"}
        )
        if r.status_code == 200 and "available" in r.text.lower():
            print(f"✓ {name}")
        time.sleep(0.5)
```

## File Reference

| File | Purpose |
|---|---|
| `pretty_names.py` | Generate and score all pronounceable 4-letter names |
| `find_available.py` | Cross-reference pretty names against BigQuery taken-username export |
| `pretty_4letter_names.csv` | Pre-generated list of 22,317 pretty names (threshold=65) |

## How the Prettiness Score Works

The score (0–100) is designed to match human intuition about what "looks good" as a username. The key insight is using **English bigram frequencies** as the primary signal — this is what separates names that *feel* like words from random character soup.

```
"hero" → he(95) + er(88) + ro(20) = high bigram avg → score 96
"bawu" → ba(5)  + aw(0)  + wu(0)  = low bigram avg  → score 68
```

Both are CVCV pattern, but "hero" uses letter combinations your brain already knows how to process.

### Score Tiers

| Tier | Score | Count | Examples |
|---|---|---|---|
| Elite | 90–100 | 550 | hero, core, care, date, fate, mare |
| Great | 80–89 | 3,047 | wren, nest, helm, vine, wine, glen |
| Good | 70–79 | 9,350 | jade, sage, dune, keen, pave, dome |
| Decent | 65–69 | 9,370 | wider pool of readable combinations |
| Below threshold | <65 | 434,659 | increasingly unpronounceable |

### Syllable Patterns (CV = Consonant/Vowel)

```
CVCV  (39%)  — luna, mika, hero, core     ← most name-like
VCVC  (16%)  — amir, evan, ikon, opus
CVCC  (15%)  — mark, dusk, ward, fern
CVVC  (11%)  — baer, deus, kaio, rein
CCVC  (10%)  — bran, frog, grim, wren
VCCV   (5%)  — arko, elma, algo
Other  (4%)  — various less common patterns
```

## Requirements

- Python 3.10+
- No external dependencies (stdlib only)
- Google account (for BigQuery, free tier)

## Efficiency Notes

- **pretty_names.py** processes all 456,976 combinations in ~3 seconds on a modern machine
- **BigQuery** scans ~24 GB per year-table (well within 1 TB/month free tier)
- The full pipeline (generate → query → cross-reference → verify) can be completed in under an hour, compared to days of API brute-forcing

## Why Not Just Use the GitHub API?

| Approach | Requests needed | Time at rate limit | Cost |
|---|---|---|---|
| GitHub API (all 4-letter) | 456,976 | ~91 hours | Free but slow |
| GitHub API (pretty only) | 22,317 | ~4.5 hours | Free but slow |
| **This pipeline** | 1 BigQuery + ~few hundred verify | **~15 minutes** | **Free** |

## Related Projects

- [ui-1/nlet](https://github.com/ui-1/nlet) — Registration endpoint checker (recommended for verification step)
- [oood/find-available-github-usernames](https://github.com/oood/find-available-github-usernames) — Pre-built dictionaries and shell scripts
- [iojw/socialscan](https://github.com/iojw/socialscan) — Multi-platform username availability checker
- [GH Archive](https://www.gharchive.org/) — The public GitHub event dataset powering Stage 2

## License

MIT

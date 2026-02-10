#!/usr/bin/env python3
"""
Generate all "pretty" / easy-to-read 4-letter GitHub username candidates.

Scoring criteria:
1. Syllable structure (CV pattern)
2. Consonant cluster legality
3. English bigram frequency (does it "look" like English?)
4. Letter pleasantness
5. Vowel distribution
6. Bonus for real-word similarity

Output: sorted list of candidates with scores, ready to cross-reference
with BigQuery GH Archive export to find available ones.
"""

import itertools
import string
import sys
from collections import Counter

VOWELS = set("aeiou")
CONSONANTS = set(string.ascii_lowercase) - VOWELS

# ── English bigram frequencies (top pairs, normalized) ──────────────
# Source: aggregated from English corpus analysis
# These represent how often letter pairs appear in English words
BIGRAM_FREQ = {
    "th": 100, "he": 95, "in": 90, "er": 88, "an": 86, "re": 84, "on": 80,
    "at": 78, "en": 76, "nd": 74, "ti": 72, "es": 70, "or": 68, "te": 66,
    "of": 64, "ed": 62, "is": 60, "it": 58, "al": 56, "ar": 54, "st": 52,
    "to": 50, "nt": 48, "ng": 46, "se": 44, "ha": 42, "as": 40, "ou": 38,
    "io": 36, "le": 34, "ve": 32, "co": 30, "me": 28, "de": 26, "hi": 24,
    "ri": 22, "ro": 20, "ic": 18, "ne": 18, "ea": 18, "ra": 18, "ce": 16,
    "li": 16, "ch": 15, "ll": 14, "be": 14, "ma": 14, "si": 13, "om": 12,
    "ur": 12, "ca": 12, "el": 12, "ta": 11, "la": 11, "ns": 10, "ge": 10,
    "ha": 10, "ho": 10, "no": 10, "pe": 10, "di": 9, "sh": 9, "lo": 9,
    "na": 9, "so": 9, "wa": 9, "da": 9, "do": 8, "mo": 8, "ni": 8,
    "pa": 8, "mi": 8, "sa": 8, "fo": 8, "fi": 7, "fa": 7, "fe": 7,
    "fu": 6, "ga": 6, "go": 6, "gi": 6, "ke": 6, "ki": 6, "ka": 6,
    "ko": 5, "ku": 5, "ba": 5, "bi": 5, "bo": 5, "bu": 5, "vi": 5,
    "va": 5, "vo": 5, "wi": 5, "we": 5, "wo": 5, "wa": 5, "ja": 4,
    "jo": 4, "ju": 4, "je": 4, "ji": 3, "ya": 3, "yo": 3, "ye": 3,
    "yi": 2, "yu": 2, "zy": 1, "za": 2, "ze": 2, "zo": 2, "zi": 2,
    "xu": 1, "xa": 1, "xe": 1, "xi": 1, "xo": 1,
    # Common consonant clusters
    "br": 8, "cr": 7, "dr": 7, "fr": 7, "gr": 7, "pr": 7, "tr": 8,
    "bl": 6, "cl": 6, "fl": 6, "gl": 5, "pl": 6, "sl": 5, "sp": 6,
    "sk": 5, "sm": 4, "sn": 4, "sw": 4, "tw": 4, "sc": 5, "wr": 3,
    "wh": 5, "kn": 3, "ph": 5,
    # Common endings
    "nt": 8, "nd": 8, "rd": 7, "rk": 6, "rn": 6, "rt": 7, "rs": 6,
    "ld": 6, "lk": 5, "lt": 6, "lm": 4, "ln": 3, "ls": 5, "lf": 4,
    "mp": 6, "nk": 5, "ft": 4, "ct": 4, "pt": 3, "sk": 5, "sp": 5,
    "ck": 7, "ss": 5,
}

# Legal consonant pairs
LEGAL_ONSETS = {
    "bl", "br", "ch", "cl", "cr", "dr", "dw", "fl", "fr", "gh", "gl", "gr",
    "kn", "ph", "pl", "pr", "sc", "sh", "sk", "sl", "sm", "sn", "sp",
    "sq", "st", "sw", "th", "tr", "tw", "wh", "wr",
}
LEGAL_CODAS = {
    "ch", "ck", "ct", "ft", "gh", "lb", "lc", "ld", "lf", "lk", "lm", "ln",
    "lp", "ls", "lt", "mb", "mp", "nc", "nd", "ng", "nk", "ns", "nt", "nx",
    "ph", "pt", "rb", "rc", "rd", "rf", "rg", "rk", "rl", "rm", "rn", "rp",
    "rs", "rt", "rv", "sh", "sk", "sp", "ss", "st", "th", "ts", "xt",
}
LEGAL_CC = LEGAL_ONSETS | LEGAL_CODAS

HARSH_LETTERS = set("qxz")
PLEASANT_ENDINGS = set("aeiounrstlm")


def get_pattern(s: str) -> str:
    return "".join("V" if c in VOWELS else "C" for c in s)


def bigram_score(s: str) -> float:
    """Average bigram frequency for the string. Higher = more English-like."""
    total = 0
    for i in range(len(s) - 1):
        pair = s[i:i+2]
        total += BIGRAM_FREQ.get(pair, 0)
    return total / (len(s) - 1)  # average over 3 bigrams


def score_name(s: str) -> float:
    """
    Score a 4-letter lowercase alpha string for prettiness.
    Returns 0-100. Higher = more pronounceable, pleasant, name-like.
    """
    s = s.lower()
    score = 0.0
    pattern = get_pattern(s)

    # ── 1. Syllable structure (0-25) ──
    PATTERN_SCORES = {
        "CVCV": 25,  # luna, mika, kobe
        "CVCC": 22,  # mark, dusk, ward
        "VCVC": 22,  # amir, evan, ikon
        "CCVC": 20,  # bran, frog, grim
        "CVVC": 20,  # baer, kaio, deus
        "VCCV": 18,  # arko, elma, algo
        "CCVV": 15,  # shoo, free, blue
        "VVCV": 14,  # aria, aura
        "VCCC": 10,  # arts, arks
        "VVCC": 10,  # oink, earn (debatable)
        "CVVV": 8,
        "VVVC": 5,
        "CCCV": 3,
        "CVVV": 8,
        "CCCC": 0,
        "VVVV": 0,
    }
    score += PATTERN_SCORES.get(pattern, 5)

    # ── 2. Bigram naturalness (0-30) ──
    bg = bigram_score(s)
    # bg ranges roughly 0-100, normalize to 0-30
    score += min(30, bg * 0.6)

    # ── 3. Consonant cluster legality (0-15) ──
    cc_penalty = 0
    for i in range(len(s) - 1):
        pair = s[i:i+2]
        c1_is_cons = pair[0] in CONSONANTS
        c2_is_cons = pair[1] in CONSONANTS
        if c1_is_cons and c2_is_cons:
            if pair in LEGAL_CC:
                pass  # fine
            elif pair[0] == pair[1]:
                cc_penalty += 5
            else:
                cc_penalty += 12
    score += max(0, 15 - cc_penalty)

    # ── 4. Vowel balance (0-10) ──
    vowel_count = sum(1 for c in s if c in VOWELS)
    vowel_scores = {0: 0, 1: 6, 2: 10, 3: 7, 4: 2}
    score += vowel_scores.get(vowel_count, 0)

    # ── 5. Letter quality (0-8) ──
    harsh_count = sum(1 for c in s if c in HARSH_LETTERS)
    score += max(0, 8 - harsh_count * 4)

    # ── 6. Ending quality (0-5) ──
    if s[-1] in PLEASANT_ENDINGS:
        score += 5

    # ── 7. Starting quality (0-3) ──
    if s[0] in CONSONANTS and s[0] not in HARSH_LETTERS:
        score += 3
    elif s[0] in VOWELS:
        score += 2

    # ── 8. Penalties ──
    # Triple consonants/vowels
    for i in range(len(s) - 2):
        chars = s[i:i+3]
        if all(c in CONSONANTS for c in chars):
            score -= 15
        if all(c in VOWELS for c in chars):
            score -= 8

    # Adjacent duplicates (less pretty: "aabb", "toot")
    for i in range(len(s) - 1):
        if s[i] == s[i+1]:
            score -= 4

    return max(0, min(100, score))


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Generate pretty 4-letter names for GitHub usernames",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --threshold 70                    # High-quality names only
  %(prog)s --threshold 60 --top 5000 -o names.csv --format csv
  %(prog)s --pattern CVCV --threshold 65     # Only consonant-vowel-consonant-vowel
  %(prog)s --threshold 50 --show-scores      # See all scores
        """)
    parser.add_argument("--threshold", type=float, default=65,
                        help="Min score 0-100 (default=65)")
    parser.add_argument("--top", type=int, default=0,
                        help="Only output top N")
    parser.add_argument("--format", choices=["txt", "csv", "json"], default="txt")
    parser.add_argument("--show-scores", action="store_true")
    parser.add_argument("--pattern", type=str, default=None,
                        help="Filter by CV pattern, e.g. CVCV, CVCC")
    parser.add_argument("-o", "--output", type=str, default=None)
    parser.add_argument("--stats-only", action="store_true",
                        help="Only show statistics")
    args = parser.parse_args()

    print(f"Generating all 456,976 four-letter combinations...", file=sys.stderr)

    results = []
    for combo in itertools.product(string.ascii_lowercase, repeat=4):
        name = ''.join(combo)
        sc = score_name(name)
        if sc >= args.threshold:
            pattern = get_pattern(name)
            if args.pattern and pattern != args.pattern:
                continue
            results.append((name, sc, pattern))

    results.sort(key=lambda x: (-x[1], x[0]))

    if args.top > 0:
        results = results[:args.top]

    # ── Stats ──
    print(f"\n{'='*50}", file=sys.stderr)
    print(f"  Threshold: {args.threshold}", file=sys.stderr)
    print(f"  Total qualifying: {len(results):,}", file=sys.stderr)

    pattern_counts = Counter(r[2] for r in results)
    print(f"  Pattern distribution:", file=sys.stderr)
    for p, c in pattern_counts.most_common(10):
        print(f"    {p}: {c:,}", file=sys.stderr)

    score_buckets = Counter()
    for _, sc, _ in results:
        bucket = int(sc // 5) * 5
        score_buckets[bucket] += 1
    print(f"  Score distribution:", file=sys.stderr)
    for bucket in sorted(score_buckets.keys(), reverse=True):
        bar = "█" * (score_buckets[bucket] // 100)
        print(f"    {bucket:3d}-{bucket+4}: {score_buckets[bucket]:>6,}  {bar}", file=sys.stderr)

    print(f"\n  Top 40 prettiest names:", file=sys.stderr)
    for name, sc, pat in results[:40]:
        print(f"    {name}  score={sc:.0f}  ({pat})", file=sys.stderr)
    print(f"{'='*50}\n", file=sys.stderr)

    if args.stats_only:
        return

    # ── Output ──
    out = open(args.output, 'w') if args.output else sys.stdout

    if args.format == "json":
        import json
        data = [{"name": r[0], "score": r[1], "pattern": r[2]} for r in results]
        json.dump(data, out, indent=2)
    elif args.format == "csv":
        out.write("name,score,pattern\n")
        for name, sc, pat in results:
            out.write(f"{name},{sc:.1f},{pat}\n")
    else:
        for name, sc, pat in results:
            if args.show_scores:
                out.write(f"{name}\t{sc:.0f}\t{pat}\n")
            else:
                out.write(f"{name}\n")

    if args.output:
        out.close()
        print(f"Written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()

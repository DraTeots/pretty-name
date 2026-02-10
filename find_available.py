#!/usr/bin/env python3
"""
Cross-reference pretty 4-letter names against a BigQuery export
of taken GitHub usernames to find available pretty names.

Usage:
  1. Export BigQuery results (taken usernames) to CSV
  2. Run: python3 find_available.py --taken bigquery_export.csv --pretty pretty_4letter_names.csv

Output: list of pretty names NOT found in the taken list
        (still need verification via GitHub registration endpoint)
"""

import csv
import sys
import argparse


def load_taken(path: str) -> set:
    """Load taken usernames from BigQuery CSV export."""
    taken = set()
    with open(path, 'r') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if row:
                taken.add(row[0].strip().lower())
    print(f"Loaded {len(taken):,} taken usernames from {path}", file=sys.stderr)
    return taken


def load_pretty(path: str) -> list:
    """Load pretty names with scores from CSV."""
    names = []
    with open(path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            names.append({
                "name": row["name"],
                "score": float(row["score"]),
                "pattern": row["pattern"]
            })
    print(f"Loaded {len(names):,} pretty names from {path}", file=sys.stderr)
    return names


def main():
    parser = argparse.ArgumentParser(description="Find available pretty GitHub usernames")
    parser.add_argument("--taken", required=True, help="BigQuery CSV export of taken usernames")
    parser.add_argument("--pretty", required=True, help="Pretty names CSV from pretty_names.py")
    parser.add_argument("--min-score", type=float, default=0, help="Min prettiness score")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    parser.add_argument("--format", choices=["txt", "csv"], default="csv")
    args = parser.parse_args()

    taken = load_taken(args.taken)
    pretty = load_pretty(args.pretty)

    # Find available
    available = [
        n for n in pretty
        if n["name"] not in taken and n["score"] >= args.min_score
    ]
    available.sort(key=lambda x: (-x["score"], x["name"]))

    print(f"\n{'='*50}", file=sys.stderr)
    print(f"  Pretty names total:     {len(pretty):,}", file=sys.stderr)
    print(f"  Taken (from BigQuery):  {len(taken):,}", file=sys.stderr)
    print(f"  Potentially available:  {len(available):,}", file=sys.stderr)
    print(f"{'='*50}", file=sys.stderr)

    if available:
        print(f"\n  Top 30 candidates:", file=sys.stderr)
        for n in available[:30]:
            print(f"    {n['name']}  score={n['score']:.0f}  ({n['pattern']})", file=sys.stderr)

    # Output
    out = open(args.output, 'w') if args.output else sys.stdout
    if args.format == "csv":
        out.write("name,score,pattern\n")
        for n in available:
            out.write(f"{n['name']},{n['score']:.1f},{n['pattern']}\n")
    else:
        for n in available:
            out.write(f"{n['name']}\n")

    if args.output:
        out.close()
        print(f"\nWritten to {args.output}", file=sys.stderr)

    print(f"""
NOTE: These are *potentially* available. BigQuery only captures
users who performed public actions. To confirm availability,
verify each candidate against GitHub's registration endpoint.
See: https://github.com/ui-1/nlet
""", file=sys.stderr)


if __name__ == "__main__":
    main()

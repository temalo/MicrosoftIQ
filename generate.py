#!/usr/bin/env python3
"""
Generate the full Contoso Events demo dataset and knowledge base.

    python generate.py                 # data CSVs + knowledge markdown
    python generate.py --data-only     # just the CSV tables
    python generate.py --knowledge-only

Outputs:
    data/output/*.csv          business data (load into a Fabric lakehouse)
    data/output/manifest.json  headline answers + row counts (used by slides)
    knowledge/files/*.md       unstructured knowledge (upload to Foundry IQ)

Everything is seeded, so results are identical on every machine.
"""

import argparse
import json
import os

from generator.model import build_model, compute_manifest
from generator.tables import write_tables
from generator.knowledge import write_knowledge

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_OUT = os.path.join(HERE, "data", "output")
KNOW_OUT = os.path.join(HERE, "knowledge", "files")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-only", action="store_true")
    ap.add_argument("--knowledge-only", action="store_true")
    args = ap.parse_args()

    print("Building deterministic model (seed fixed)...")
    tables = build_model()
    manifest = compute_manifest(tables)

    if not args.knowledge_only:
        counts = write_tables(tables, DATA_OUT)
        with open(os.path.join(DATA_OUT, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"\nData -> {DATA_OUT}")
        for k, v in counts.items():
            print(f"  {k:<20} {v:>8,} rows")

    if not args.data_only:
        files = write_knowledge(tables, manifest, KNOW_OUT)
        print(f"\nKnowledge -> {KNOW_OUT}")
        for f in files:
            print(f"  {f}")

    print("\nHeadline answers (reproducible):")
    ts = manifest["top_speakers_by_licensed_users_attended"]
    tsp = manifest["top_sponsors_by_influenced_pipeline"]
    print("  Top speaker by licensed users attended: "
          f"{ts[0][0]} ({ts[0][1]:,})")
    print("  Top sponsor by influenced pipeline:      "
          f"{tsp[0][0]} (${tsp[0][1]:,.0f}, {tsp[0][2]}x)")
    print("  Licensed-user definition spread:         "
          + ", ".join(f"{k}={v:,}" for k, v in
                      manifest["licensed_user_definitions"].items()))


if __name__ == "__main__":
    main()

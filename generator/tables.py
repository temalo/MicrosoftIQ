"""Write every table in the model to a CSV file under a target directory."""

import csv
import os


def write_tables(tables, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    written = {}
    for name, rows in tables.items():
        path = os.path.join(out_dir, f"{name}.csv")
        if not rows:
            open(path, "w").close()
            written[name] = 0
            continue
        # union of keys preserves column order from the first row
        fields = list(rows[0].keys())
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        written[name] = len(rows)
    return written

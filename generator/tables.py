"""Write every table in the model to a CSV file under a target directory."""

import csv
import io
import os


def write_tables(tables, out_dir, overwrite=False):
    os.makedirs(out_dir, exist_ok=True)
    pending = {}
    for name, rows in tables.items():
        path = os.path.join(out_dir, f"{name}.csv")
        output = io.StringIO(newline="")
        if rows:
            w = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        text = output.getvalue()
        if os.path.exists(path):
            with open(path, newline="", encoding="utf-8") as existing:
                if existing.read() == text:
                    continue
            if not overwrite:
                raise FileExistsError(f"Refusing to replace changed data: {path}; use --overwrite after review")
        pending[path] = text
    # Preflight every table before changing any of them.
    for path, text in pending.items():
        with open(path, "w" if overwrite else "x", newline="", encoding="utf-8") as handle:
            handle.write(text)
    return {name: len(rows) for name, rows in tables.items()}

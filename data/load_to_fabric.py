# Fabric notebook: load the demo CSVs into the lakehouse as Delta tables.
#
# HOW TO USE
#   1. Run `python generate.py` locally to produce data/output/*.csv.
#   2. In your Fabric workspace, open the lakehouse and upload every CSV from
#      data/output/ into  Files/seed/  (drag-and-drop, or use OneLake tools).
#   3. Create a notebook, attach it to the lakehouse, paste this file's contents
#      into a cell, and run. It writes one managed Delta table per CSV.
#
# The table names match the ontology / semantic-model expectations exactly.

from pyspark.sql import SparkSession

spark = SparkSession.builder.getOrCreate()

# Folder (inside the attached lakehouse's Files) that holds the uploaded CSVs.
SEED_DIR = "Files/seed"

TABLES = [
    "businessunit", "role", "product", "entitlement", "org",
    "user", "userlicence",
    "conference", "speaker", "session", "sessionspeaker",
    "registration", "sessionattendance",
    "sponsor", "conferencesponsor", "sessionfeedback", "conferencefinance",
]

for name in TABLES:
    path = f"{SEED_DIR}/{name}.csv"
    print(f"Loading {path} ...")
    df = (spark.read
          .option("header", "true")
          .option("inferSchema", "true")
          .csv(path))
    # 'user' is a reserved word in some SQL dialects; the lakehouse handles it,
    # but you may prefer to rename it to 'appuser' here and everywhere downstream.
    df.write.mode("overwrite").format("delta").saveAsTable(name)
    print(f"  -> table `{name}`  ({df.count():,} rows, {len(df.columns)} cols)")

print("\nAll tables loaded. Build the semantic model on top of these tables.")

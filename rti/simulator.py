"""Deterministic synthetic badge scans. No cloud writes occur on import.

Run locally: python -m rti.simulator --help
Fabric: upload this file and schema.json together; see simulate_badge_scans.ipynb.
"""

import argparse
import csv
import dataclasses
import datetime as dt
import hashlib
import io
import json
import math
import os
from pathlib import Path
import random
import re
import time
import uuid

UTC = dt.timezone.utc
SCHEMA = json.loads(Path(__file__).with_name("schema.json").read_text(encoding="utf-8"))
SOURCE_TABLES = ("conference", "sponsor", "conferencesponsor", "user",
                 "registration", "userlicence")
TIER_WEIGHT = {"Platinum": 3.0, "Gold": 2.0, "Silver": 1.0,
               "Bronze": 0.75, "Startup": 0.5}
SCAN_TYPES = ("Booth Visit", "Collateral Download", "Raffle Entry",
              "Demo Request", "Meeting Booked")


def utc(value):
    if isinstance(value, str):
        value = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone offset")
    return value.astimezone(UTC)


def iso(value):
    return utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def load_csv(folder):
    tables = {}
    for name in SOURCE_TABLES:
        with (Path(folder) / f"{name}.csv").open(encoding="utf-8", newline="") as handle:
            tables[name] = list(csv.DictReader(handle))
    return tables


def _index(rows, key):
    result = {}
    for row in rows:
        value = int(row[key])
        if value in result:
            raise ValueError(f"Duplicate {key}: {value}")
        result[value] = row
    return result


def derive_dimensions(tables):
    """One booth per sponsorship; one synthetic scanner per booth, never random."""
    sponsors = _index(tables["sponsor"], "SponsorId")
    conferences = _index(tables["conference"], "ConferenceId")
    sponsorships = _index(tables["conferencesponsor"], "ConferenceSponsorId")
    booths, devices = [], []
    for bid, row in sorted(sponsorships.items()):
        cid, sid = int(row["ConferenceId"]), int(row["SponsorId"])
        if cid not in conferences or sid not in sponsors:
            raise ValueError("Sponsorship references an unknown conference or sponsor")
        if row["Tier"] not in TIER_WEIGHT:
            raise ValueError(f"Unsupported sponsorship tier: {row['Tier']}")
        booths.append({
            "BoothId": bid, "ConferenceSponsorId": bid, "ConferenceId": cid,
            "SponsorId": sid, "SponsorName": sponsors[sid]["Name"], "Tier": row["Tier"],
            "BoothCode": f"EXPO-{cid}-{bid:04d}",
        })
        devices.append({"DeviceId": f"SCN-{bid:05d}", "BoothId": bid,
                        "ConferenceId": cid, "DeviceType": "Synthetic badge reader"})
    if not booths:
        raise ValueError("No sponsorships to simulate")
    return booths, devices


@dataclasses.dataclass(frozen=True)
class Config:
    run_id: str
    start: dt.datetime
    seed: int = 20260915
    batches: int = 12
    interval_seconds: float = 5.0
    scans_per_minute: float = 6.0
    conference_id: int = 0  # 0 includes all model conferences
    outage_booth_id: int = 0
    outage_start_seconds: float = 600.0
    outage_end_seconds: float = 1200.0

    def __post_init__(self):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", self.run_id):
            raise ValueError("RunId must be 1-80 letters, digits, underscores or hyphens")
        object.__setattr__(self, "start", utc(self.start))
        if not isinstance(self.batches, int) or self.batches <= 0:
            raise ValueError("batches must be a positive finite integer")
        for name in ("interval_seconds", "scans_per_minute",
                     "outage_start_seconds", "outage_end_seconds"):
            if not math.isfinite(getattr(self, name)):
                raise ValueError(f"{name} must be finite")
        if self.interval_seconds <= 0 or self.scans_per_minute < 0:
            raise ValueError("interval must be positive; rate must be nonnegative")
        if not 0 <= self.outage_start_seconds < self.outage_end_seconds:
            raise ValueError("Outage must be a nonempty half-open nonnegative interval")
        if self.outage_booth_id and self.outage_start_seconds >= self.duration:
            raise ValueError("Outage starts after the run ends")

    @property
    def duration(self):
        return self.batches * self.interval_seconds


class Simulator:
    def __init__(self, tables, config):
        self.config = config
        all_booths, all_devices = derive_dimensions(tables)
        users = _index(tables["user"], "UserId")
        conferences = _index(tables["conference"], "ConferenceId")
        self.registrants = {}
        for row in tables["registration"]:
            cid, uid = int(row["ConferenceId"]), int(row["UserId"])
            if cid not in conferences or uid not in users:
                raise ValueError("Registration has a broken foreign key")
            self.registrants.setdefault(cid, set()).add(uid)
        self.registrants = {k: sorted(v) for k, v in self.registrants.items()}
        self.licensed = set()
        for row in tables["userlicence"]:
            uid = int(row["UserId"])
            if uid not in users:
                raise ValueError("Licence references an unknown user")
            if row["Status"] == "Active":
                self.licensed.add(uid)
        self.booths = [b for b in all_booths if
                       not config.conference_id or b["ConferenceId"] == config.conference_id]
        if not self.booths or any(b["ConferenceId"] not in self.registrants for b in self.booths):
            raise ValueError("Selected conferences must have booths and registered users")
        bids = {b["BoothId"] for b in self.booths}
        if config.outage_booth_id and config.outage_booth_id not in bids:
            raise ValueError("Outage booth is not in the selected conferences")
        self.devices = [d for d in all_devices if d["BoothId"] in bids]
        self.device_by_booth = {d["BoothId"]: d["DeviceId"] for d in self.devices}
        identity = {"booths": self.booths, "devices": self.devices,
                    "registrants": self.registrants, "licensed": sorted(self.licensed)}
        self.model_hash = hashlib.sha256(json.dumps(
            identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def run_info(self):
        c = self.config
        config_json = dataclasses.asdict(c)
        config_json["start"] = iso(c.start)
        return {"RunId": c.run_id, "Seed": c.seed, "ModelHash": self.model_hash,
                "StartedAt": iso(c.start),
                "PlannedEndAt": iso(c.start + dt.timedelta(seconds=c.duration)),
                "ConfigJson": json.dumps(config_json, sort_keys=True)}

    def batches(self):
        c = self.config
        rng = random.Random(c.seed)
        for batch in range(c.batches):
            rows = []
            lo, hi = batch * c.interval_seconds, (batch + 1) * c.interval_seconds
            for booth in self.booths:
                rate = c.scans_per_minute * TIER_WEIGHT[booth["Tier"]] / 60.0
                if not rate:
                    continue
                # Events on a deterministic rate lattice, in [lo, hi).
                for ordinal in range(math.ceil(lo * rate), math.ceil(hi * rate)):
                    offset = ordinal / rate
                    bid, cid = booth["BoothId"], booth["ConferenceId"]
                    uid = rng.choice(self.registrants[cid])
                    scan_type = rng.choices(SCAN_TYPES, weights=(60, 16, 12, 8, 4))[0]
                    opt_in = rng.random() < 0.65
                    stamp = iso(c.start + dt.timedelta(seconds=offset))
                    row = {
                        "ScanId": str(uuid.uuid5(uuid.NAMESPACE_URL,
                            f"contoso-events:{c.run_id}:{c.seed}:{bid}:{ordinal}")),
                        "RunId": c.run_id, "Seed": c.seed, "ScanTimestamp": stamp,
                        "ConferenceId": cid, "BoothId": bid, "SponsorId": booth["SponsorId"],
                        "UserId": uid, "DeviceId": self.device_by_booth[bid],
                        "ScanType": scan_type, "DwellSeconds": rng.randint(3, 120),
                        "IsLicensedUser": uid in self.licensed,
                        "OptInShareContact": opt_in,
                        "IsQualified": opt_in and scan_type in ("Demo Request", "Meeting Booked"),
                        "IsSynthetic": True,
                    }
                    if bid == c.outage_booth_id and c.outage_start_seconds <= offset < c.outage_end_seconds:
                        continue
                    rows.append(row)
            yield sorted(rows, key=lambda r: (r["ScanTimestamp"], r["BoothId"], r["ScanId"]))


def validate_rows(table, rows):
    fields = SCHEMA["tables"][table]["columns"]
    for row in rows:
        if set(row) != set(fields):
            raise ValueError(f"{table} fields do not match schema")
        for name, kind in fields.items():
            value = row[name]
            valid = ((kind == "string" and isinstance(value, str)) or
                     (kind == "long" and type(value) is int and -(2**63) <= value < 2**63) or
                     (kind == "bool" and type(value) is bool))
            if kind == "datetime":
                utc(value)
                valid = True
            if not valid:
                raise ValueError(f"{table}.{name}: expected {kind}")


def json_lines(rows):
    return "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)


class JsonSink:
    def __init__(self, output, run_id):
        self.folder = Path(output) / run_id
        self.folder.mkdir(parents=True, exist_ok=False)
        self.handle = None

    def prepare(self, sim):
        for name, rows in (("BoothDim", sim.booths), ("ScanDevice", sim.devices),
                           ("RunInfo", [sim.run_info()])):
            validate_rows(name, rows)
            (self.folder / f"{name}.jsonl").write_text(json_lines(rows), encoding="utf-8")
        self.handle = (self.folder / "BadgeScan.jsonl").open("x", encoding="utf-8")

    def send(self, rows):
        self.handle.write(json_lines(rows))
        self.handle.flush()

    def close(self):
        if self.handle:
            self.handle.close()


class DeltaSink:
    """Append only; fail if dimensions differ or RunId was previously reserved."""
    def __init__(self, spark):
        self.spark = spark
        spark.conf.set("spark.sql.session.timeZone", "UTC")

    def frame(self, table, rows):
        from pyspark.sql import types as T
        kinds = {"string": T.StringType, "long": T.LongType,
                 "bool": T.BooleanType, "datetime": T.TimestampType}
        fields = SCHEMA["tables"][table]["columns"]
        schema = T.StructType([T.StructField(k, kinds[v](), False) for k, v in fields.items()])
        cooked = [{k: utc(v) if fields[k] == "datetime" else v for k, v in row.items()}
                  for row in rows]
        return self.spark.createDataFrame(cooked, schema)

    def prepare(self, sim):
        from pyspark.sql import functions as F
        # Existing tables may contain other conferences; verify this run's keys.
        for name, rows in (("BoothDim", sim.booths), ("ScanDevice", sim.devices)):
            table = name.lower()
            expected = self.frame(name, rows)
            if self.spark.catalog.tableExists(table):
                existing = self.spark.read.table(table).select(*expected.columns)
                key = SCHEMA["tables"][name]["key"]
                selected = existing.join(expected.select(*key), key, "inner")
                if (selected.exceptAll(expected).limit(1).count() or
                        expected.exceptAll(selected).limit(1).count()):
                    raise ValueError(f"{table} differs; use a clean demo lakehouse, not overwrite")
            else:
                expected.write.mode("errorifexists").format("delta").saveAsTable(table)
        if self.spark.catalog.tableExists("runinfo"):
            if self.spark.table("runinfo").where(F.col("RunId") == sim.config.run_id).limit(1).count():
                raise ValueError("RunId already exists; use a new RunId (no implicit replay)")
        self.frame("RunInfo", [sim.run_info()]).write.mode("append").format("delta").saveAsTable("runinfo")

    def send(self, rows):
        self.frame("BadgeScan", rows).write.mode("append").format("delta").saveAsTable("badgescan")

    def close(self):
        pass


class EventhouseSink:
    """Direct streaming, Entra auth, no token persisted; transport failures propagate."""
    def __init__(self, cluster, database, credential=None):
        from azure.identity import DefaultAzureCredential
        from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
        from azure.kusto.ingest import KustoStreamingIngestClient
        from urllib.parse import urlparse
        parsed = urlparse(cluster)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
                parsed.password or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
            raise ValueError("KUSTO_CLUSTER must be an HTTPS cluster origin")
        if not re.fullmatch(r"[A-Za-z0-9_-]+", database):
            raise ValueError("Use a simple demo database name")
        self.credential = credential or DefaultAzureCredential()
        self.owns_credential = credential is None
        # Let the SDK discover the correct cloud token audience, not the cluster URL.
        kcsb = KustoConnectionStringBuilder.with_azure_token_credential(
            cluster, credential=self.credential)
        self.query = KustoClient(kcsb)
        self.ingest = KustoStreamingIngestClient(kcsb)
        self.database = database

    def _send(self, table, rows):
        from azure.kusto.data import DataFormat
        from azure.kusto.ingest import IngestionProperties, IngestionStatus
        properties = IngestionProperties(
            database=self.database, table=table, data_format=DataFormat.MULTIJSON,
            ingestion_mapping_reference=table + "Mapping")
        payload = json_lines(rows).encode()
        if len(payload) > 3 * 1024 * 1024:
            raise ValueError("Batch exceeds demo streaming payload limit; reduce rate/interval")
        result = self.ingest.ingest_from_stream(io.BytesIO(payload), ingestion_properties=properties)
        if result.status != IngestionStatus.SUCCESS:
            raise RuntimeError(f"Streaming ingestion did not succeed: {result.status}")

    def prepare(self, sim):
        # Eventhouse dimension ingestion is a separate explicit setup step.
        for name, expected in (("BoothDim", sim.booths), ("ScanDevice", sim.devices)):
            response = self.query.execute(self.database, name)
            actual = [row.to_dict() for row in response.primary_results[0]]
            key = SCHEMA["tables"][name]["key"][0]
            indexed = {row[key]: row for row in actual}
            if len(indexed) != len(actual) or any(indexed.get(row[key]) != row for row in expected):
                raise ValueError(f"Load and verify matching, unique {name} before streaming")
        found = self.query.execute(self.database,
            f"RunInfo | where RunId == '{sim.config.run_id}' | count")
        if found.primary_results[0][0][0]:
            raise ValueError("RunId already exists; use a new RunId")
        self._send("RunInfo", [sim.run_info()])

    def send(self, rows):
        self._send("BadgeScan", rows)

    def close(self):
        self.query.close()
        self.ingest.close()
        if self.owns_credential:
            self.credential.close()


def run(sim, sink, realtime=True):
    """Finite run. Reserve identity first. No silent retries or swallowed failures."""
    count = 0
    try:
        for name, rows in (("BoothDim", sim.booths), ("ScanDevice", sim.devices),
                           ("RunInfo", [sim.run_info()])):
            validate_rows(name, rows)
        sink.prepare(sim)
        for index, rows in enumerate(sim.batches()):
            if realtime:
                deadline = sim.config.start + dt.timedelta(
                    seconds=(index + 1) * sim.config.interval_seconds)
                time.sleep(max(0, (deadline - dt.datetime.now(UTC)).total_seconds()))
            validate_rows("BadgeScan", rows)
            if rows:
                sink.send(rows)
            count += len(rows)
            print(f"batch={index + 1}/{sim.config.batches} accepted_for_ingestion={len(rows)} total={count}")
    finally:
        sink.close()
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("json", "eventhouse"), default="json")
    parser.add_argument("--csv-dir", default="data/output")
    parser.add_argument("--output", default="data/output/rti")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--start", default=None, help="Offset-aware ISO timestamp; default UTC now")
    parser.add_argument("--seed", type=int, default=20260915)
    parser.add_argument("--batches", type=int, default=12)
    parser.add_argument("--interval-seconds", type=float, default=5)
    parser.add_argument("--scans-per-minute", type=float, default=6)
    parser.add_argument("--conference-id", type=int, default=0)
    parser.add_argument("--outage-booth-id", type=int, default=0)
    parser.add_argument("--outage-start-seconds", type=float, default=600)
    parser.add_argument("--outage-end-seconds", type=float, default=1200)
    parser.add_argument("--no-sleep", action="store_true", help="Offline replay only; timestamps are not live")
    args = parser.parse_args()
    start = utc(args.start) if args.start else dt.datetime.now(UTC)
    config = Config(run_id=args.run_id or ("run-" + uuid.uuid4().hex), start=start,
                    seed=args.seed, batches=args.batches, interval_seconds=args.interval_seconds,
                    scans_per_minute=args.scans_per_minute, conference_id=args.conference_id,
                    outage_booth_id=args.outage_booth_id, outage_start_seconds=args.outage_start_seconds,
                    outage_end_seconds=args.outage_end_seconds)
    sim = Simulator(load_csv(args.csv_dir), config)
    sink = (JsonSink(args.output, config.run_id) if args.mode == "json" else
            EventhouseSink(os.environ["KUSTO_CLUSTER"], os.environ["KUSTO_DATABASE"]))
    print(f"RunId={config.run_id} ModelHash={sim.model_hash}")
    run(sim, sink, realtime=not args.no_sleep)


if __name__ == "__main__":
    main()

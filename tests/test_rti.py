import contextlib
import copy
import datetime as dt
import io
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import types
import unittest
from unittest import mock
import uuid

from generator.model import build_model, compute_manifest
from generator.tables import write_tables
from rti.simulator import (Config, EventhouseSink, JsonSink, SCHEMA, Simulator,
                           TIER_WEIGHT, UTC, derive_dimensions, iso, json_lines,
                           load_csv, run, utc, validate_rows)

ROOT = Path(__file__).resolve().parents[1]
START = dt.datetime(2026, 9, 15, 12, tzinfo=UTC)


@contextlib.contextmanager
def workspace():
    # Only project-local scratch; never use the OS temp directory.
    folder = ROOT / "tests" / (".work-" + uuid.uuid4().hex)
    folder.mkdir()
    try:
        yield folder
    finally:
        shutil.rmtree(folder)


def quiet_reference(sim, rows, end, window=300, freshness=60):
    """Independent local oracle for the documented KQL scenario, not a KQL engine."""
    end = utc(end)
    cutoff = end - dt.timedelta(seconds=window)
    start = cutoff - dt.timedelta(seconds=window)
    counts = {b["BoothId"]: [0, 0] for b in sim.booths}
    stamps = []
    for row in rows:
        stamp = utc(row["ScanTimestamp"])
        if stamp < end:
            stamps.append(stamp)
        if start <= stamp < end:
            counts[row["BoothId"]][int(stamp >= cutoff)] += 1
    fresh = bool(stamps) and max(stamps) >= end - dt.timedelta(seconds=freshness)
    warm = end >= sim.config.start + dt.timedelta(seconds=2 * window)
    within_run = end <= sim.config.start + dt.timedelta(seconds=sim.config.duration)
    flags = {}
    for booth in sim.booths:
        previous, current = counts[booth["BoothId"]]
        peers = [b for b in sim.booths if b["BoothId"] != booth["BoothId"]
                 and b["ConferenceId"] == booth["ConferenceId"] and b["Tier"] == booth["Tier"]]
        peer_previous = sum(counts[b["BoothId"]][0] for b in peers)
        peer_current = sum(counts[b["BoothId"]][1] for b in peers)
        flags[booth["BoothId"]] = bool(
            fresh and warm and within_run and previous >= 10 and len(peers) >= 2
            and peer_previous > 0 and current / previous <= 0.3
            and peer_current / peer_previous >= 0.7)
    return counts, flags, fresh


class SimulatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tables = build_model()

    def sim(self, **kwargs):
        return Simulator(self.tables, Config(run_id="test-run", start=START, **kwargs))

    def test_dimensions_are_exact_model_derivations(self):
        booths, devices = derive_dimensions(self.tables)
        sponsors = {s["SponsorId"]: s["Name"] for s in self.tables["sponsor"]}
        sources = {s["ConferenceSponsorId"]: s for s in self.tables["conferencesponsor"]}
        self.assertEqual(booths, self.tables["boothdim"])
        self.assertEqual(devices, self.tables["scandevice"])
        for booth, device in zip(booths, devices):
            source = sources[booth["BoothId"]]
            self.assertEqual(booth["SponsorName"], sponsors[source["SponsorId"]])
            for key in ("ConferenceId", "SponsorId", "Tier"):
                self.assertEqual(booth[key], source[key])
            self.assertEqual(device["DeviceId"], f"SCN-{booth['BoothId']:05d}")
            self.assertEqual(device["BoothId"], booth["BoothId"])
            self.assertEqual(device["ConferenceId"], booth["ConferenceId"])

    def test_deterministic_independent_of_source_order(self):
        sim = self.sim()
        reordered = {name: list(reversed(rows)) for name, rows in self.tables.items()}
        other = Simulator(reordered, sim.config)
        self.assertEqual(sim.run_info(), other.run_info())
        self.assertEqual(json_lines(sum(sim.batches(), [])), json_lines(sum(other.batches(), [])))

    def test_schema_keys_and_every_foreign_key(self):
        sim = self.sim()
        rows = sum(sim.batches(), [])
        tables = {**self.tables, "BoothDim": sim.booths, "ScanDevice": sim.devices,
                  "RunInfo": [sim.run_info()], "BadgeScan": rows}
        for name, schema in SCHEMA["tables"].items():
            validate_rows(name, tables[name])
            keys = [tuple(row[k] for k in schema["key"]) for row in tables[name]]
            self.assertEqual(len(keys), len(set(keys)), name)
        for fk in SCHEMA["foreignKeys"]:
            targets = {tuple(row[k] for k in fk["references"]) for row in tables[fk["to"]]}
            self.assertTrue(all(tuple(row[k] for k in fk["columns"]) in targets
                                for row in tables[fk["from"]]), str(fk))

    def test_qualification_is_independent_of_licensing(self):
        sim = self.sim(batches=120)
        rows = sum(sim.batches(), [])
        for row in rows:
            self.assertEqual(row["IsQualified"], row["OptInShareContact"] and
                             row["ScanType"] in ("Demo Request", "Meeting Booked"))
            self.assertEqual(row["IsLicensedUser"], row["UserId"] in sim.licensed)
            self.assertTrue(row["IsSynthetic"])
        self.assertTrue(any(r["IsQualified"] and not r["IsLicensedUser"] for r in rows))

    def test_all_batches_are_half_open_utc_and_unique(self):
        for rate in (0, 0.3, 6, 7.1, 23.7):
            with self.subTest(rate=rate):
                sim = self.sim(scans_per_minute=rate, interval_seconds=3.7, batches=37)
                seen = set()
                for n, batch in enumerate(sim.batches()):
                    lo = START + dt.timedelta(seconds=n * 3.7)
                    hi = START + dt.timedelta(seconds=(n + 1) * 3.7)
                    for row in batch:
                        self.assertLessEqual(lo, utc(row["ScanTimestamp"]))
                        self.assertLess(utc(row["ScanTimestamp"]), hi)
                        self.assertTrue(row["ScanTimestamp"].endswith("Z"))
                        self.assertNotIn(row["ScanId"], seen)
                        seen.add(row["ScanId"])

    def test_rate_counts_and_zero_rate(self):
        sim = self.sim()
        rows = sum(sim.batches(), [])
        for booth in sim.booths:
            expected = math.ceil(sim.config.duration * sim.config.scans_per_minute *
                                 TIER_WEIGHT[booth["Tier"]] / 60)
            self.assertEqual(sum(r["BoothId"] == booth["BoothId"] for r in rows), expected)
        self.assertEqual(sum(self.sim(scans_per_minute=0).batches(), []), [])

    def test_run_seed_and_snapshot_identity(self):
        sim = self.sim()
        first = sum(sim.batches(), [])
        other = Simulator(self.tables, Config(run_id="another-run", start=START))
        self.assertTrue({r["ScanId"] for r in first}.isdisjoint(
            r["ScanId"] for r in sum(other.batches(), [])))
        changed = self.sim(seed=11)
        self.assertNotEqual(first, sum(changed.batches(), []))
        self.assertEqual(sim.model_hash, other.model_hash)
        self.assertEqual(sim.run_info()["StartedAt"], iso(START))
        self.assertEqual(utc(sim.run_info()["PlannedEndAt"]) - START, dt.timedelta(minutes=1))

    def test_timezone_and_invalid_config(self):
        self.assertEqual(utc("2026-09-15T14:00:00+02:00"), START)
        for bad in (dt.datetime(2026, 1, 1), "2026-01-01T00:00:00"):
            with self.assertRaises(ValueError):
                utc(bad)
        for changes in ({"batches": 0}, {"interval_seconds": 0},
                        {"scans_per_minute": -1}, {"scans_per_minute": math.inf},
                        {"scans_per_minute": math.nan}, {"outage_booth_id": 2},
                        {"outage_start_seconds": -1}, {"outage_end_seconds": 0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.sim(**changes)
        with self.assertRaises(ValueError):
            Config(run_id="unsafe'query", start=START)

    def test_bad_foreign_keys_and_unknown_scope_fail(self):
        for table, field in (("registration", "UserId"), ("registration", "ConferenceId"),
                             ("conferencesponsor", "SponsorId"), ("userlicence", "UserId")):
            bad = copy.deepcopy(self.tables)
            bad[table][0][field] = -999
            with self.subTest(table=table, field=field), self.assertRaises(ValueError):
                Simulator(bad, Config("bad", START))
        with self.assertRaises(ValueError):
            self.sim(conference_id=999)
        with self.assertRaises(ValueError):
            self.sim(outage_booth_id=999, outage_start_seconds=0)

    def test_duplicates_and_unknown_tiers_fail(self):
        bad = copy.deepcopy(self.tables)
        bad["conferencesponsor"].append(bad["conferencesponsor"][0])
        with self.assertRaises(ValueError):
            derive_dimensions(bad)
        bad = copy.deepcopy(self.tables)
        bad["conferencesponsor"][0]["Tier"] = "Unknown"
        with self.assertRaises(ValueError):
            derive_dimensions(bad)

    def test_one_booth_outage_does_not_reallocate_other_traffic(self):
        baseline = self.sim(conference_id=1, batches=250)
        outage = self.sim(conference_id=1, batches=250, outage_booth_id=2)
        expected, actual = sum(baseline.batches(), []), sum(outage.batches(), [])
        self.assertEqual([r for r in expected if r["BoothId"] != 2],
                         [r for r in actual if r["BoothId"] != 2])
        for row in actual:
            if row["BoothId"] == 2:
                seconds = (utc(row["ScanTimestamp"]) - START).total_seconds()
                self.assertFalse(600 <= seconds < 1200)
        self.assertTrue(any(r["BoothId"] == 2 and utc(r["ScanTimestamp"]) >=
                            START + dt.timedelta(seconds=1200) for r in actual))
        counts, flags, fresh = quiet_reference(outage, actual, START + dt.timedelta(minutes=15))
        self.assertEqual(counts[2], [30, 0])
        self.assertEqual([bid for bid, flag in flags.items() if flag], [2])
        self.assertTrue(fresh)

    def test_warmup_stream_stopped_and_zero_denominators(self):
        sim = self.sim(conference_id=1, batches=240, outage_booth_id=2)
        rows = sum(sim.batches(), [])
        _, flags, _ = quiet_reference(sim, rows, START + dt.timedelta(minutes=8))
        self.assertFalse(any(flags.values()))
        stopped = [r for r in rows if utc(r["ScanTimestamp"]) < START + dt.timedelta(minutes=13)]
        _, flags, fresh = quiet_reference(sim, stopped, START + dt.timedelta(minutes=15))
        self.assertFalse(fresh)
        self.assertFalse(any(flags.values()))
        counts, flags, fresh = quiet_reference(sim, [], START + dt.timedelta(minutes=15))
        self.assertEqual(len(counts), len(sim.booths))
        self.assertFalse(any(flags.values()))
        self.assertFalse(fresh)
        _, flags, _ = quiet_reference(sim, rows, START + dt.timedelta(minutes=21))
        self.assertFalse(any(flags.values()))

    def test_json_files_roundtrip_and_collision(self):
        with workspace() as folder:
            sim = self.sim()
            with contextlib.redirect_stdout(io.StringIO()):
                count = run(sim, JsonSink(folder, "test-run"), realtime=False)
            rows = [json.loads(line) for line in
                    (folder / "test-run" / "BadgeScan.jsonl").read_text().splitlines()]
            self.assertEqual(count, len(rows))
            self.assertEqual(rows, sum(sim.batches(), []))
            with self.assertRaises(FileExistsError):
                JsonSink(folder, "test-run")

    def test_sink_failure_surfaces_and_closes(self):
        sink = mock.Mock()
        sink.send.side_effect = OSError("simulated transport failure")
        with self.assertRaisesRegex(OSError, "simulated transport failure"):
            run(self.sim(), sink, realtime=False)
        sink.send.assert_called_once()
        sink.close.assert_called_once()
        sink = mock.Mock()
        sink.prepare.side_effect = ValueError("prepare failed")
        with self.assertRaisesRegex(ValueError, "prepare failed"):
            run(self.sim(), sink, realtime=False)
        sink.send.assert_not_called()
        sink.close.assert_called_once()

    def test_realtime_sleep_uses_batch_deadline(self):
        sink = mock.Mock()
        sim = Simulator(self.tables, Config("clock-test", dt.datetime.now(UTC), batches=1))
        with mock.patch("rti.simulator.time.sleep") as sleep, contextlib.redirect_stdout(io.StringIO()):
            run(sim, sink, realtime=True)
        self.assertGreater(sleep.call_args.args[0], 0)
        self.assertLessEqual(sleep.call_args.args[0], 5)

    def test_csv_export_is_non_destructive_and_loadable(self):
        with workspace() as folder:
            write_tables(self.tables, folder)
            loaded = Simulator(load_csv(folder), self.sim().config)
            self.assertEqual(loaded.model_hash, self.sim().model_hash)
            self.assertEqual(sum(loaded.batches(), []), sum(self.sim().batches(), []))
            times = {p.name: p.stat().st_mtime_ns for p in folder.iterdir()}
            write_tables(self.tables, folder)
            self.assertEqual(times, {p.name: p.stat().st_mtime_ns for p in folder.iterdir()})
            path = folder / "sponsor.csv"
            path.write_text("user data", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                write_tables(self.tables, folder)
            self.assertEqual(path.read_text(), "user data")

    def test_cli_replay_success_and_collision_exit_code(self):
        with workspace() as folder:
            write_tables(self.tables, folder)
            command = [sys.executable, "-m", "rti.simulator", "--csv-dir", str(folder),
                       "--output", str(folder / "events"), "--run-id", "cli-test",
                       "--start", iso(START), "--batches", "2", "--no-sleep"]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = folder / "events" / "cli-test" / "BadgeScan.jsonl"
            before = output.read_bytes()
            retry = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(retry.returncode, 0)
            self.assertEqual(before, output.read_bytes())

    def test_original_headlines_are_preserved(self):
        manifest = compute_manifest(self.tables)
        shipped = json.loads((ROOT / "data" / "output" / "manifest.json").read_text())
        for key in ("licensed_user_definitions", "distinct_active_licensed_users",
                    "top_speakers_by_licensed_users_attended", "top_sponsors_by_influenced_pipeline"):
            self.assertEqual(json.loads(json.dumps(manifest[key])), shipped[key])

    def test_strict_schema_rejects_missing_extra_and_wrong_types(self):
        row = sum(self.sim(batches=1).batches(), [])[0]
        for changes in ({"IsQualified": 1}, {"BoothId": "1"}, {"Seed": 2**64},
                        {"Unexpected": True}, {"ScanTimestamp": "2026-01-01T00:00:00"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_rows("BadgeScan", [{**row, **changes}])

    def test_streaming_sdk_failure_is_not_reported_as_success(self):
        module = types.ModuleType("azure.kusto.ingest")
        data_module = types.ModuleType("azure.kusto.data")
        data_module.DataFormat = types.SimpleNamespace(MULTIJSON="multijson")
        module.IngestionProperties = lambda **kwargs: kwargs
        module.IngestionStatus = types.SimpleNamespace(SUCCESS="Success")
        sink = EventhouseSink.__new__(EventhouseSink)
        sink.database = "ContosoEventsRTI"
        sink.ingest = mock.Mock()
        sink.ingest.ingest_from_stream.return_value = types.SimpleNamespace(status="Failed")
        with mock.patch.dict("sys.modules", {"azure.kusto.ingest": module,
                                           "azure.kusto.data": data_module}):
            with self.assertRaisesRegex(RuntimeError, "did not succeed"):
                sink.send([{"ScanId": "synthetic"}])
            sink.ingest.ingest_from_stream.side_effect = OSError("network failed")
            with self.assertRaisesRegex(OSError, "network failed"):
                sink.send([{"ScanId": "synthetic"}])
            with self.assertRaisesRegex(ValueError, "payload limit"):
                sink.send([{"large": "x" * (3 * 1024 * 1024)}])


class AssetTests(unittest.TestCase):
    def test_notebook_json_metadata_and_code_compile(self):
        notebook = json.loads((ROOT / "rti" / "simulate_badge_scans.ipynb").read_text())
        self.assertEqual(notebook["nbformat"], 4)
        self.assertEqual(notebook["metadata"]["kernelspec"]["name"], "synapse_pyspark")
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                self.assertIsNone(cell["execution_count"])
                self.assertEqual(cell["outputs"], [])
                compile("".join(cell["source"]), "<notebook-cell>", "exec")
        self.assertNotIn("default_lakehouse", json.dumps(notebook["metadata"]))

    def test_kql_table_and_json_mapping_contract(self):
        text = (ROOT / "rti" / "setup.kql").read_text()
        definitions = re.findall(r"^\.create table (\w+) \(([^)]+)\)$", text, re.M)
        mappings = re.findall(r"^\.create table (\w+) ingestion json mapping '(\w+)' '(.+)'$", text, re.M)
        self.assertEqual(len(definitions), len(SCHEMA["tables"]))
        self.assertEqual(len(mappings), len(SCHEMA["tables"]))
        for name, columns in definitions:
            actual = dict(field.strip().split(":") for field in columns.split(","))
            self.assertEqual(actual, SCHEMA["tables"][name]["columns"])
        for name, mapping, body in mappings:
            self.assertEqual(mapping, name + "Mapping")
            columns = json.loads(body)
            self.assertEqual({c["column"] for c in columns}, set(SCHEMA["tables"][name]["columns"]))
            for column in columns:
                self.assertEqual(column["Properties"]["Path"], "$." + column["column"])

    def test_kql_has_no_unsupported_numeric_long_suffixes(self):
        for name in ("dashboard.kql", "functions.kql"):
            with self.subTest(file=name):
                text = (ROOT / "rti" / name).read_text()
                self.assertNotRegex(text, r"\b\d+[Ll]\b")

    def test_kql_query_safety_contract(self):
        text = (ROOT / "rti" / "functions.kql").read_text()
        self.assertIn("join kind=leftouter Counts on BoothId, ConferenceId", text)
        self.assertIn("by ConferenceId, Tier", text)
        self.assertIn("PeerCount=TierBooths - 1", text)
        self.assertIn("PeerPrevious > 0", text)
        self.assertIn("Eligible=StreamFresh and Warm and WithinRun", text)
        self.assertIn("ScanTimestamp < _end", text)
        self.assertNotIn("between", text)
        dashboard = (ROOT / "rti" / "dashboard.kql").read_text()
        self.assertEqual(len(re.findall(r"^// [1-6]\.", dashboard, re.M)), 6)
        self.assertIn("NOT a true conversion funnel", dashboard)

    def test_binding_and_metadata_probe_are_explicit_not_deployments(self):
        mapping = json.loads((ROOT / "agent" / "ontology-bindings.json").read_text())
        self.assertIn("specification", mapping["kind"])
        for relation in mapping["relationships"]:
            self.assertEqual(len(relation["sourceColumns"]), len(relation["targetColumns"]))
        probe = json.loads((ROOT / "agent" / "metadata-probe.json").read_text())
        self.assertEqual(len(probe["sources"]), 1)
        self.assertEqual(probe["sources"][0]["type"], "ontology")
        self.assertIn("CE-17", probe["sources"][0]["elements"][0]["description"])


if __name__ == "__main__":
    unittest.main()

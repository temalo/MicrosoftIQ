# Contoso Events — Real-Time Intelligence

This is a **synthetic, finite, reproducible demonstration**, not a production
visitor-tracking system. No commands in this repository provision cloud resources
automatically. Latency depends on capacity, ingestion, refresh and query settings;
there is **no subsecond guarantee**.

## What runs where

| Mode | Output | Prerequisites |
|---|---|---|
| Local JSON (default CLI) | Four JSONL files in a new run directory | Python standard library |
| Delta microbatches (default notebook) | `boothdim`, `scandevice`, `runinfo`, `badgescan` | Attached Fabric Spark lakehouse |
| Eventhouse direct streaming | `RunInfo`, `BadgeScan`; dimensions loaded separately | KQL tables/mappings, streaming policy, Entra identity |

**Delta and Eventhouse are independent and are not automatically synchronized.**
Delta writes do not appear in KQL. KQL writes do not update Direct Lake. Neither
adding an Eventstream item nor adding an ontology relationship wires ingestion.
The optional Eventstream/azure-eventhub producer is **not implemented** here; use
direct Eventhouse streaming or implement and review that separate endpoint route.
Do not assume a custom endpoint, destination, field mapping or secret is configured.

## Reproducible local quickstart

From the repository root:

```powershell
python generate.py --data-only
python -m rti.simulator --run-id sample-01 --start 2026-09-15T12:00:00Z --no-sleep
python -m unittest discover -s tests -v
```

Default simulation: 12 five-second microbatches; nominal 6 scans/minute **per booth**
times illustrative tier weights: Platinum 3, Gold 2, Silver 1, Bronze 0.75,
Startup 0.5. Events are on a deterministic rate lattice (not a Poisson arrival
model), so low rates can produce empty batches. `--scans-per-minute 0` is valid.
Use `--batches`, `--interval-seconds`, `--scans-per-minute`, `--conference-id`
and `--seed` to control the run. Conference 0 means all; defaults are finite.
These are scenario rates, not measured traffic or a staffing plan.

Fix **RunId, seed, start, config and model snapshot** for byte-identical events.
Without overrides, start is timezone-aware UTC now and RunId is unique. Timestamps
are event time, on `[start, start + duration)`; they need not match the historical
conference dates. `RunInfo` records the seed, input-model hash, UTC start, planned
end and full config. Planned end is not proof of completion. No real contact data
is emitted; `UserId` is a synthetic key, not a license to share identifying data.

Every output directory is created exclusively. An existing run fails rather than
overwriting or silently resuming. Sinks stop and surface exceptions on failed
writes. A partial run remains partial: use a new RunId after diagnosing it.
There is no distributed lock or exactly-once guarantee: never run two producers
with one RunId. On timeout, acceptance can be uncertain. Check sink rows before
retrying; KQL functions deduplicate by ScanId. Do not retry with a new ID and
combine both runs in one tile. Delta appends likewise need explicit deduplication
if you manually replay outside the supplied runner.

## Model and schema

[`schema.json`](schema.json) is the explicit type/key/FK contract used by Python
and checked against KQL in tests. Lakehouse names are lower-case; KQL names are
case-sensitive. Datetimes use ISO 8601 UTC JSON and Spark TimestampType with UTC
session timezone. Keys use 64-bit integers except RunId, ScanId and DeviceId.

- **BoothDim**: one row per `conferencesponsor.ConferenceSponsorId`; BoothId equals
  that key. ConferenceId/SponsorId come from that same row; label comes from
  `sponsor.Name`, tier from `conferencesponsor.Tier`. BoothCode is synthetic
  `EXPO-{ConferenceId}-{BoothId:04d}` because this model has no BoothNumber.
- **ScanDevice**: exactly one synthetic device per BoothId, `SCN-{BoothId:05d}`;
  its conference is inherited from that booth, never randomly associated.
- **BadgeScan**: one interaction, referencing the booth's sponsor/conference,
  that booth's device and a registered user in that conference.
- **IsLicensedUser**: snapshot membership in users with any `userlicence.Status`
  equal to `Active`. Independent of scan type and opt-in; not a historical
  point-in-time licence validity calculation.
- **IsQualified**: `OptInShareContact AND ScanType IN ("Demo Request",
  "Meeting Booked")`. **Licensing is NOT part of this flag**.
  **Licensed-qualified / CE-17 eligibility** additionally requires
  `IsLicensedUser`. Distinguish these two metrics everywhere.
- Interactions are sampled independently, not ordered stages of a user journey.
  The interaction chart is a **mix, not a true conversion funnel**.

`generate.py` includes `boothdim.csv` and `scandevice.csv` in the generic model.
The base loader refuses existing tables by default. Use a dedicated demo
lakehouse; explicitly opt into replacement only after reviewing the existing data.
The local CSV exporter skips byte-identical files and refuses changed CSVs or
manifest unless `generate.py --overwrite` is explicitly supplied. Knowledge
markdown remains regenerable via the existing knowledge writer; use `--data-only`
to preserve locally edited knowledge.

## Import the Fabric notebook

1. Run the generic generator and base loader per [`agent/setup.md`](../agent/setup.md).
2. Import [`simulate_badge_scans.ipynb`](simulate_badge_scans.ipynb) into Fabric.
   Choose a supported Spark runtime and **attach your default lakehouse**.
   The notebook includes Synapse PySpark kernelspec and language metadata, but
   deliberately contains no workspace/lakehouse IDs. Save after attachment so
   Fabric writes the actual default-lakehouse metadata.
3. Upload `simulator.py` and `schema.json` to that lakehouse's `Files/rti/`.
4. Review config and dimension preview. Delta mode needs no additional packages.
   It checks existing dimension values, reserves the RunId, and appends events.
   Existing mismatched dimensions fail rather than being overwritten.
5. Run the last cell deliberately. Clear outputs before exporting a notebook.
   Add the new Delta tables, relationships and measures to the semantic model;
   **table writes alone do not update model selection or publish the Data Agent**.

## Direct Eventhouse streaming (alternative)

1. Manually create/select a **demo** Eventhouse KQL database. Verify query and
   streaming ingestion permissions for the intended Entra identity.
2. Run each command in [`setup.kql`](setup.kql) separately. They create tables,
   JSON ingestion mappings and enable streaming ingestion for the two event/run
   tables. Review existing schemas/policies first; do not replace existing data.
3. Produce a local JSON run and use Fabric **Get data → Local file** to load
   `BoothDim.jsonl` and `ScanDevice.jsonl` into their corresponding tables with the
   supplied JSON mappings. They are newline-delimited JSON (one object per line).
   Upload each dimension only once. Alternatively load generated dimension CSVs
   with explicit column/type selections in the wizard (not JSON mappings).
   Do not assume Delta dimensions have been replicated to KQL.
4. Verify counts and joins:

   ```kusto
   BoothDim | summarize Rows=count(), Keys=dcount(BoothId)
   ScanDevice | summarize Rows=count(), Keys=dcount(DeviceId)
   ScanDevice | join kind=leftanti BoothDim on BoothId, ConferenceId
   // Must return no rows; use exact count() by key to investigate duplicates.
   BoothDim | summarize Rows=count() by BoothId | where Rows != 1
   ```

5. Install optional dependencies: `pip install -r rti/requirements-eventhouse.txt`.
   For Fabric, attach a published Environment with those dependencies. Provide
   `KUSTO_CLUSTER` (query cluster HTTPS origin) and `KUSTO_DATABASE` via environment
   variables. These are configuration, not credentials. The producer uses
   `DefaultAzureCredential`: locally use approved Azure CLI sign-in; in Fabric use
   an approved available identity or pass an Azure `TokenCredential` implementation.
   Notebook support for identity mechanisms varies; a missing credential fails.
   **Never put a token, client secret or connection string in code/notebook/output**.
   Do not hardcode tenant endpoints or fetch using embedded credentials.
6. Run `python -m rti.simulator --mode eventhouse --conference-id 1` with a new
   RunId (or select Eventhouse in the notebook). The producer verifies loaded
   dimensions and refuses an observed existing RunId. Streaming SDK failures
   propagate; success means ingestion accepted, not a latency SLA. Verify:

   ```kusto
   BadgeScan | summarize Rows=count(), LastEvent=max(ScanTimestamp) by RunId
   ```

7. Deploy each function in [`functions.kql`](functions.kql). Copy one numbered
   block from [`dashboard.kql`](dashboard.kql) per tile. Bind RunId/ConferenceId
   explicitly; use `now()` live, a fixed UTC `_end` for replay.

For an **offline dashboard replay**, also load `RunInfo.jsonl` and `BadgeScan.jsonl`
with their mappings, only once into the chosen demo database. This is manual
ingestion, not the direct-streaming producer. Never use a historical replay to
claim current freshness or measured end-to-end latency.

## Reproduce one booth going quiet

The shipped model's BoothId **2**, ConferenceId **1**, is Silver with four other
Silver booths in that conference (verify preview if you change the model).

```powershell
python -m rti.simulator --run-id quiet-demo --start 2026-09-15T12:00:00Z --conference-id 1 --batches 240 --outage-booth-id 2 --outage-start-seconds 600 --outage-end-seconds 1200 --no-sleep
```

This suppresses **only BoothId 2** for `[12:10,12:20)`; other booths keep their
configured rate, with no traffic reallocation. At `_end=datetime(2026-09-15T12:15:00Z)`,
the previous window is `[12:05,12:10)` and current is `[12:10,12:15)`.
The provided rule uses min previous 10 scans, at least 2 same-tier peers, a 70%
drop and peer retention >=70%; it should identify this constructed example.
Thresholds are illustrative, configurable and **not guaranteed flags** on arbitrary
seeds, volumes, tiers or data. For live streaming omit `--start` and `--no-sleep`,
use a new RunId and substitute its actual timeline. Extend batches beyond 240
to demonstrate recovery after second 1200.

Tiles retain ConferenceId and BoothId. Dimension LEFT JOINs include zero-scan
booths; division by zero returns null. The quiet rule excludes self from its
same-conference/tier peer baseline; it requires two full warm-up windows, a fresh
event somewhere in the conference/run, and an unexpired planned run.
If **the whole stream stops**, `StreamFresh=false`; individual candidates are
suppressed. Treat missing/stale data as a separate pipeline-health investigation.
Freshness is event-time based and conservative around ingestion delay: inspect
ingestion health separately. It is not a device heartbeat or diagnosis of cause.

## Activator: manual review, not auto-provisioned or activated

This package creates **no Activator item, rule, recipient, email or Teams message**.
After validating dashboard results and configuring supported query refresh:

1. Manually create an Activator item/rule from the supported dashboard/data source
   path in your Fabric experience. Include RunId + ConferenceId + BoothId as the
   object identity (add the selected RunId to the outgoing query projection).
2. Filter to `QuietCandidate == true` only after health/warm-up checks. Decide
   sustained-duration, cooldown and reset behavior; preview events, including
   all-stream-stopped and no-traffic cases.
3. Preview the exact alert text with aggregate counts and synthetic booth labels.
   **Confirm recipients and obtain approval before enabling actions.** Configure
   least privilege, consent, retention and access policy for any real deployment.
4. Do not automatically share badge/user/contact rows. Opt-in demo data is not
   authorization to disclose PII; real consent scope and withdrawals need separate
   governance. Activation remains an explicit operator action.

## Validation boundary

Standard-library tests cover deterministic generation, schema/FKs, IDs, rate and
outage behavior, UTC windows, failure propagation, JSON output protection,
notebook code compilation, and KQL table/mapping consistency. KQL expressions,
Spark/Delta execution, Entra streaming ingestion, dashboard rendering, Activator
and published-agent routing still require validation in your selected Fabric
environment. No cloud deployment was performed by the local validation suite.

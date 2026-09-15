# Microsoft IQ — Conferences demo (Contoso Events)

An end-to-end, reproducible demo of the **"Microsoft IQ"** pattern: a single
conversational agent that answers both **quantitative** questions (from governed
data) and **qualitative** questions (from unstructured knowledge), and always
tells you which source it used.

It's built for a fictitious events company, **Contoso Events**, that runs eight
conferences a year. Two headline questions drive the whole story:

- **"Which speakers had the most licensed users attend?"** → a ranking from the data
- **"What sponsors drove the most value?"** → influenced pipeline + ROI from the data
- …plus blended questions like *"Which speaker drew the most licensed users, and
  what's their background?"* that need **both** sources.

Everything is synthetic and **seeded**, so the same top speaker, top sponsor, and
licensed-user numbers appear on every machine. The optional **Real-Time
Intelligence (RTI)** package adds synthetic badge scans, booth/device dimensions,
Delta microbatches or independent Eventhouse streaming, KQL dashboard tiles and a
reproducible single-booth outage scenario.

## The architecture

```
generate.py ──CSV──► Fabric Lakehouse ──► Direct Lake semantic model ──┐
                         │                                          │
                         └── explicit bindings ──► Ontology         │
                                                   (runtime limits) │
RTI simulator ── Delta OR independent Eventhouse KQL source ─────────┤
                                                                    ▼
                                                           Fabric Data Agent
                                                                    │
generate.py ──markdown──► Foundry IQ Knowledge ─────────────► Foundry orchestrator
                                                                    │
                                                        Teams / M365 / web client
```

The orchestrator routes numbers → the **Fabric Data Agent**, descriptions → the
**Foundry IQ** knowledge base, and blends both for mixed questions.
See **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** for a fuller diagram.

## What's in the box

| Path | What it is |
|------|-----------|
| `generate.py` | Generates the whole dataset + knowledge base (seeded, reproducible) |
| `generator/` | The model (single source of truth), CSV exporter, knowledge writer |
| `data/` | `load_to_fabric.py` (PySpark loader) + `schema.md` (tables & relationships) |
| `knowledge/files/` | 13 markdown files to upload to Foundry IQ |
| `agent/` | Orchestrator + Fabric Data Agent instructions, ontology, semantic model, **setup.md** |
| `app/` | Zero-dependency Node web client for the published agent |
| `slides/` | A data-driven pitch deck (`build_slides.py`) |
| `rti/` | Importable Fabric notebook, reusable simulator, explicit schema, KQL setup/functions/dashboard |
| `tests/` | Standard-library validation for simulator, schema, assets and failure paths |

## Quickstart

```bash
# 1. Generate the data + knowledge (stdlib only)
python generate.py

# 2. Stand up the platform (Fabric + Foundry) — follow the guide:
#    agent/setup.md   (lakehouse → semantic model → ontology → Data Agent
#                       → Foundry IQ knowledge → orchestrator agent)

# 3. Run the web client against your published agent
cd app && cp ../.env.example .env    # edit .env with your Foundry values
node server.js                       # http://localhost:3000

# 4. (Optional) build the pitch deck
pip install -r requirements.txt
cd slides && python build_slides.py
```

Full step-by-step instructions: **[agent/setup.md](agent/setup.md)**.

## New: synthetic badge scans and RTI

```powershell
python generate.py --data-only
python -m rti.simulator --run-id sample-01 --start 2026-09-15T12:00:00Z --no-sleep
python -m unittest discover -s tests -v
```

Import **[rti/simulate_badge_scans.ipynb](rti/simulate_badge_scans.ipynb)** into
Fabric and attach your own default lakehouse. Follow **[rti/README.md](rti/README.md)**
for direct Eventhouse streaming, dimension loading, KPI/pulse/leaderboard/
interaction-mix/peer/quiet-booth queries and an outage walkthrough.
Existing output runs are never overwritten by default.

- `IsQualified` = opted-in demo/meeting; **licensed-qualified additionally requires
  active licensing**. Badge interactions are synthetic, not a conversion funnel.
- Delta and Eventhouse are independent, **not automatically synchronized**.
  An Eventstream item alone is not wired. No subsecond latency guarantee.
- Live KQL requires **adding the KQL database to the Data Agent and republishing**;
  the existing semantic-model path cannot read it.
- Ontology relationship declarations require actual instance binding. The
  [metadata-only probe](agent/metadata-grounding.md) remains unavailable in the
  observed Standard runtime; this repo does not claim working metadata grounding.
- Activator is **not provisioned or activated**. Preview alerts, confirm recipients
  and obtain approval; never automatically share contacts.

## Reproducible headline answers

After `python generate.py`, `data/output/manifest.json` records the exact answers
for the shipped seed — the top speaker by licensed users attended, the top sponsor
by influenced pipeline, and the four licensed-user definition counts
(658 / 749 / 2,294 / 3,484). The knowledge files and the deck reference the same
entities, so data and narrative always agree.

## Requirements

- **Python 3.9+** (generator is standard-library only; `python-pptx` only for slides)
- **Node 18+** (web client; no `npm install` needed)
- **Azure CLI** (`az`) for the device-code sign-in and RBAC
- A **Microsoft Fabric** capacity and an **Azure AI Foundry** resource
- Optional direct streaming dependencies: `rti/requirements-eventhouse.txt`.
  Delta uses Fabric's supplied Spark runtime; local JSON/tests need no packages.

The current pitch deck covers the original historical data/knowledge story.
Its RTI, Activator and metadata-grounding claims have not been expanded; use the
RTI walkthrough for those features rather than assuming the deck demonstrates them.

## A note on the data

All names, numbers, conferences, speakers and sponsors are **synthetic**.
**"Contoso Events"** is a fictitious company; any resemblance to real
organizations, people, or products is coincidental. This repository is a
technical demonstration and is not an official Microsoft product.

## License

[MIT](LICENSE).

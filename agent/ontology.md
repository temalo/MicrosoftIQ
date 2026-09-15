# Ontology (Fabric IQ)

The Fabric IQ ontology gives the model a business vocabulary — typed entities and
named relationships — on top of the lakehouse tables. This is the intended
vocabulary layer, not a claim that all runtimes can answer from its descriptions.
The semantic model answers historical/Delta numbers; explicitly selected KQL
answers Eventhouse RTI. See [metadata-grounding.md](metadata-grounding.md) for
the observed ontology-only Standard-runtime limitation.

## Entity types

**Licensed-user core (7):**

| Entity | Bound table | Notes |
|--------|-------------|-------|
| `User` | `user` | the 5,000-person pool |
| `Role` | `role` | user's job role |
| `BusinessUnit` | `businessunit` | owns a licensed-user definition |
| `Licence` | `userlicence` | a user's product licence |
| `Product` | `product` | licensable product |
| `Org` | `org` | client organization a licence belongs to |
| `Entitlement` | `entitlement` | what a product tier grants |

**Conference extension (6):**

| Entity | Bound table |
|--------|-------------|
| `Conference` | `conference` |
| `Speaker` | `speaker` |
| `Session` | `session` |
| `Sponsor` | `sponsor` |
| `Registration` | `registration` |
| `Attendance` | `sessionattendance` |

## Relationships (verbs)

Core:
- `BusinessUnit` — supports → `User`
- `BusinessUnit` — supports → `Product`
- `User` — has → `Role`
- `User` — has → `Licence`
- `User` — uses → `Product`
- `Licence` — belongs to → `Org`
- `Product` — has → `Entitlement`

Conference:
- `Conference` — features → `Session`
- `Session` — presented by → `Speaker`
- `User` — registers for → `Conference` (via `Registration`)
- `User` — attends → `Session` (via `Attendance`)
- `Conference` — sponsored by → `Sponsor`
- `Registration` — for → `User`

## Build notes

- Create the ontology in the same workspace, bound to the `ConferencesData`
  lakehouse (OneLake).
- Bind each entity type to its table and map the key + descriptive properties.
- The ontology intentionally holds **no measures** — keep all aggregation in the
  selected semantic model or KQL source rather than inferring tool support.

## RTI extension and explicit instance binding

Add **Booth**, **ScanDevice**, **BadgeScan** entity types with the keys, properties
and relationship endpoints in [ontology-bindings.json](ontology-bindings.json).
This is a human-reviewed mapping specification, **not an auto-deployment payload**.
It also identifies bridges for existing conference/sponsor, session/speaker,
registration and attendance relationships.

Native **relationship type declarations do not imply FK-name automatic joins**.
Actual entity data binding and relationship **instance-binding setup is required**
in the supported Fabric experience/API for your runtime. Map each source/target
key explicitly, including all composite components listed, materialize the needed
relationship source/bridge if required, and validate a sample traversal and orphan
counts before claiming it works. Keys should be unique on entity tables.

Map `sponsor.Name` to the Booth SponsorName property and
`conferencesponsor.Tier` to Tier. Active licensing is `userlicence.Status = Active`.
`BadgeScan.IsQualified` means opted-in demo/meeting; licensing is independent.
Choose the Delta binding for the notebook's Delta path. An Eventhouse table is not
automatically instance-bound through a same-named Delta table or this JSON spec.

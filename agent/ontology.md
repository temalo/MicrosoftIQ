# Ontology (Fabric IQ)

The Fabric IQ ontology gives the model a business vocabulary — typed entities and
named relationships — on top of the lakehouse tables. It answers *definitional*
and *relationship* questions ("what is a licensed user", "how do speakers relate
to attendees"); the semantic model answers the numbers.

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
  semantic model so the Data Agent routes numeric questions there.

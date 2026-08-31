# Data model & schema

The demo dataset has two layers that share the same 5,000-person user pool:

1. **Licensed-user model** — the "one question, four answers" story: how many
   *licensed users* do we have? Four business units define it differently.
2. **Conference model** — eight conferences, their speakers, sessions,
   attendance, sponsors and finances, built on the same users.

All tables are generated deterministically by `generate.py` (fixed seed), so the
headline answers are identical on every run.

## Tables

### Licensed-user model (ontology base)

| Table | Grain | Key columns |
|-------|-------|-------------|
| `businessunit` | one row per BU | `BusinessUnitId`, `Name` |
| `role` | one row per role | `RoleId`, `Name` |
| `product` | one row per product | `ProductId`, `Name` |
| `entitlement` | product × tier | `EntitlementId`, `ProductId`, `Tier` |
| `org` | client organization | `OrgId`, `Name`, `Segment` |
| `user` | 5,000 users | `UserId`, `BusinessUnitId`, `RoleId`, `OrgId`, `PrimaryProductId`, and four definition flags |
| `userlicence` | user × licence | `UserLicenceId`, `UserId`, `ProductId`, `EntitlementId`, `OrgId`, `Status` |

The four **licensed-user definition flags** on `user` (nested populations):

| Flag | Business unit | Definition | Count |
|------|---------------|------------|-------|
| `NamedLicensedUser` | Sales | Named licensed user | 658 |
| `PaidLicensedSeat` | Finance | Paid licensed seat | 749 |
| `ServedPopulation` | Global Service & Delivery | Served population | 2,294 |
| `LoginCapableIdentity` | Shared Services | Login-capable identity | 3,484 |

"Licensed" for the **conference** measures means a user with at least one
`Active` row in `userlicence` (~4,300 users).

### Conference model

| Table | Grain | Key columns |
|-------|-------|-------------|
| `conference` | 8 conferences | `ConferenceId`, `Name`, `Theme`, `City`, dates |
| `speaker` | 60 speakers | `SpeakerId`, `FullName`, `Affiliation`, `Expertise` |
| `session` | ~130 sessions | `SessionId`, `ConferenceId`, `Title`, `Track`, `SessionType` |
| `sessionspeaker` | session × speaker | `SessionId`, `SpeakerId`, `Role` |
| `registration` | user × conference | `RegistrationId`, `ConferenceId`, `UserId`, `RegType`, `Status` |
| `sessionattendance` | user × session | `SessionAttendanceId`, `SessionId`, `ConferenceId`, `UserId`, `DwellMinutes` |
| `sponsor` | 30 sponsors | `SponsorId`, `Name`, `Industry` |
| `conferencesponsor` | conference × sponsor | `Tier`, `SponsorshipFeeUSD`, `LeadsQualified`, `InfluencedPipelineUSD`, `ClosedWonUSD` |
| `sessionfeedback` | survey response | `SessionId`, `Rating`, `NPS` |
| `conferencefinance` | one row per conference | revenue, cost, margin |

## Key relationships

```
businessunit 1─* user
role         1─* user
org          1─* user
product      1─* user (PrimaryProductId)
product      1─* entitlement
user         1─* userlicence
org          1─* userlicence

conference   1─* session
conference   1─* registration
conference   1─* sessionattendance
conference   1─* conferencesponsor
conference   1─1 conferencefinance
session      1─* sessionspeaker
session      1─* sessionattendance
session      1─* sessionfeedback
speaker      1─* sessionspeaker
sponsor      1─* conferencesponsor
user         1─* registration
user         1─* sessionattendance
```

## The two headline questions → the joins that answer them

- **"Which speakers had the most licensed users attend?"**
  `speaker → sessionspeaker → session → sessionattendance → user`,
  counting **distinct** `UserId` where the user is licensed (active `userlicence`).
  Semantic-model measure: `Licensed Users Attended` (uses `TREATAS` to push the
  licensed-user set onto attendance).

- **"What sponsors drove the most value?"**
  `sponsor → conferencesponsor`, summing `InfluencedPipelineUSD` (and
  `ClosedWonUSD`), with ROI = influenced ÷ `SponsorshipFeeUSD`.

The exact top results for the shipped seed are recorded in
`data/output/manifest.json` after you run the generator.

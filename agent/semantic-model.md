# Semantic model (Direct Lake)

Build a Direct Lake semantic model over the `ConferencesData` lakehouse. The
model holds the relationships and historical/Delta measures. Eventhouse RTI
queries require a separately selected KQL Data Agent source; this model cannot
read KQL merely because matching entity names exist.

## Relationships to create

The arrows below identify **FK → key**, not filter flow. Use single-direction
filtering from the one-side dimension to the many-side fact. Do not enable
bidirectional filtering to make bridge measures work.

- `user[BusinessUnitId]` → `businessunit[BusinessUnitId]`
- `user[RoleId]` → `role[RoleId]`
- `user[OrgId]` → `org[OrgId]`
- `userlicence[UserId]` → `user[UserId]`
- `userlicence[ProductId]` → `product[ProductId]`
- `entitlement[ProductId]` → `product[ProductId]`
- `session[ConferenceId]` → `conference[ConferenceId]`
- `sessionspeaker[SessionId]` → `session[SessionId]`
- `sessionspeaker[SpeakerId]` → `speaker[SpeakerId]`
- `registration[ConferenceId]` → `conference[ConferenceId]`
- `registration[UserId]` → `user[UserId]`
- `sessionattendance[SessionId]` → `session[SessionId]`
- `sessionattendance[UserId]` → `user[UserId]`
- `sessionattendance[ConferenceId]` → `conference[ConferenceId]` **inactive**:
  the active conference → session → attendance path already provides filtering.
- `conferencesponsor[ConferenceId]` → `conference[ConferenceId]`
- `conferencesponsor[SponsorId]` → `sponsor[SponsorId]`
- `sessionfeedback[SessionId]` → `session[SessionId]`
- `conferencefinance[ConferenceId]` → `conference[ConferenceId]`

## Measures (DAX)

```dax
-- Distinct licensed users who attended (respects a Speaker / Conference filter).
-- Self-contained via TREATAS so it works regardless of cross-filter direction.
Licensed Users Attended =
VAR LicensedUsers =
    CALCULATETABLE ( VALUES ( userlicence[UserId] ), userlicence[Status] = "Active" )
VAR ScopedSessions =
    CALCULATETABLE ( VALUES ( sessionspeaker[SessionId] ) )
RETURN
CALCULATE (
    DISTINCTCOUNT ( sessionattendance[UserId] ),
    KEEPFILTERS ( TREATAS ( LicensedUsers, sessionattendance[UserId] ) ),
    KEEPFILTERS ( TREATAS ( ScopedSessions, sessionattendance[SessionId] ) )
)

Distinct Attendees        = DISTINCTCOUNT ( sessionattendance[UserId] )
Total Registrations       = COUNTROWS ( registration )
Influenced Pipeline (USD) = SUM ( conferencesponsor[InfluencedPipelineUSD] )
Closed Won (USD)          = SUM ( conferencesponsor[ClosedWonUSD] )
Sponsorship Fees (USD)    = SUM ( conferencesponsor[SponsorshipFeeUSD] )
Sponsor ROI               = DIVIDE ( [Influenced Pipeline (USD)], [Sponsorship Fees (USD)] )
Leads Qualified           = SUM ( conferencesponsor[LeadsQualified] )
Avg Session Rating        = AVERAGE ( sessionfeedback[Rating] )
Total Revenue (USD)       = SUM ( conferencefinance[TotalRevenueUSD] )
Total Margin (USD)        = SUM ( conferencefinance[MarginUSD] )

-- The "one question, four answers" licensed-user definitions:
Named Licensed Users      = SUM ( 'user'[NamedLicensedUser] )
Paid Licensed Seats       = SUM ( 'user'[PaidLicensedSeat] )
Served Population         = SUM ( 'user'[ServedPopulation] )
Login-Capable Identities  = SUM ( 'user'[LoginCapableIdentity] )
```

## Verifying the headline answers

- Group **`Licensed Users Attended`** by `speaker[FullName]`, sort descending →
  the top speaker matches `manifest.json`.
- Group **`Influenced Pipeline (USD)`** (and `Sponsor ROI`) by `sponsor[Name]`,
  sort descending → the top sponsor matches `manifest.json`.
- The four definition measures return 658 / 749 / 2,294 / 3,484.

> Note: `user` and `session` can be reserved words in some tooling. Direct Lake
> handles them, but if you hit issues, rename the tables (e.g. `appuser`,
> `confsession`) consistently across the loader, ontology and measures.

## RTI Delta extension (explicit selection required)

Select `boothdim`, `scandevice`, `badgescan`, `runinfo` in the semantic model
after they exist. Select the new tables/measures in the Data Agent source
metadata and republish. Use the keys from `rti/schema.json`:

| Active relationship (one → many) | Notes |
|---|---|
| `conference[ConferenceId]` → `boothdim[ConferenceId]` | Conference filter path for scans |
| `sponsor[SponsorId]` → `boothdim[SponsorId]` | Sponsor filter path |
| `boothdim[BoothId]` → `badgescan[BoothId]` | Unique booth key |
| `scandevice[DeviceId]` → `badgescan[DeviceId]` | Device filter only |
| `user[UserId]` → `badgescan[UserId]` | User filter only |
| `runinfo[RunId]` → `badgescan[RunId]` | Select exactly one run for scenario comparisons |

Keep direct conference/sponsor → badgescan relationships **inactive or absent**.
Keep boothdim → scandevice and conferencesponsor → boothdim **inactive or absent**.
Their FKs remain valid, but activating all of them creates duplicate filter paths.
Do not activate a second route just because an ontology relationship exists.
Hide redundant fact foreign keys from report authors; use dimensions for slicers.

```dax
Badge Scans = DISTINCTCOUNT ( badgescan[ScanId] )

Qualified Badge Scans =
CALCULATE (
    [Badge Scans],
    KEEPFILTERS ( badgescan[IsQualified] = TRUE () )
)

Licensed Qualified Badge Scans =
CALCULATE (
    [Qualified Badge Scans],
    KEEPFILTERS ( badgescan[IsLicensedUser] = TRUE () )
)

Qualified Scan Share = DIVIDE ( [Qualified Badge Scans], [Badge Scans] )

Badge Scans Last 5 Minutes =
VAR WindowEnd = UTCNOW ()
RETURN
    CALCULATE (
        [Badge Scans],
        KEEPFILTERS ( badgescan[ScanTimestamp] >= WindowEnd - 5 / 1440 ),
        KEEPFILTERS ( badgescan[ScanTimestamp] < WindowEnd )
    )
```

`IsQualified` means opted-in demo/meeting, independent of licensing.
`Licensed Qualified Badge Scans` adds the active-license snapshot flag (CE-17).
Do not sum these counts with the historical `conferencesponsor[LeadsQualified]`;
they are different synthetic facts. Live measures depend on model/query refresh;
use explicit fixed UTC filters for historical replay rather than UTCNOW().

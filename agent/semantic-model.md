# Semantic model (Direct Lake)

Build a Direct Lake semantic model over the `ConferencesData` lakehouse. The
model holds the relationships and the measures; the Fabric Data Agent answers all
numeric questions from here.

## Relationships to create

Single-direction (many → one) unless noted:

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
- `sessionattendance[ConferenceId]` → `conference[ConferenceId]`
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
    TREATAS ( LicensedUsers, sessionattendance[UserId] ),
    TREATAS ( ScopedSessions, sessionattendance[SessionId] )
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

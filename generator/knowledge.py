"""
Generate the unstructured knowledge base (markdown) from the same model that
produces the business data, so speaker names, sponsor names, conferences and
packages always match the tables. Upload these files to Foundry IQ.
"""

import os

BRAND = "Contoso Events"

PACKAGE_BENEFITS = {
    "Platinum": ("$250,000", [
        "Premium exhibition booth in the prime expo location",
        "A mainstage keynote or premium breakout speaking slot",
        "Expo listing, mobile-app placement and lead scanning",
        "10 full-conference passes",
        "Logo on mainstage and event signage",
    ]),
    "Gold": ("$120,000", [
        "Exhibition booth in a high-traffic aisle",
        "A breakout speaking slot",
        "Expo listing, mobile-app placement and lead scanning",
        "6 full-conference passes",
    ]),
    "Silver": ("$55,000", [
        "Standard exhibition booth",
        "Expo listing and lead scanning",
        "3 full-conference passes",
    ]),
    "Bronze": ("$22,000", [
        "Shared exhibition kiosk",
        "Expo listing",
        "2 full-conference passes",
    ]),
    "Startup": ("$8,000", [
        "Startup-alley kiosk",
        "Expo listing",
        "1 full-conference pass",
    ]),
}


def _w(out_dir, name, text):
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text.rstrip() + "\n")
    return name


def write_knowledge(tables, manifest, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    files = []
    files.append(_readme(out_dir, tables))
    for c in tables["conference"]:
        files.append(_conference_guide(out_dir, c, tables))
    files.append(_speaker_directory(out_dir, tables, manifest))
    files.append(_sponsor_prospectus(out_dir, tables, manifest))
    files.append(_attendee_faq(out_dir))
    files.append(_policies(out_dir))
    return files


def _readme(out_dir, tables):
    lines = [
        f"# {BRAND} Conference Knowledge Base", "",
        "This is the unstructured knowledge layer for the "
        f"{BRAND} \u201cMicrosoft IQ\u201d demo. Foundry IQ ingests these files "
        "to answer qualitative questions (speaker backgrounds, session and track "
        "descriptions, per-conference guides, the sponsor prospectus, the attendee "
        "FAQ and event policies), while the Fabric Data Agent answers the "
        "quantitative questions from the lakehouse tables.", "",
        "## Contents", "",
        "- `speaker-directory.md` \u2014 all speakers, expertise and bios",
        "- `sponsor-prospectus.md` \u2014 sponsorship packages and the sponsor roster",
        "- `attendee-faq.md` \u2014 registration, passes, virtual attendance, refunds",
        "- `policies-and-guidelines.md` \u2014 code of conduct, recording, data use",
    ]
    for c in tables["conference"]:
        lines.append(f"- `conference-{c['ConferenceId']}-guide.md` "
                     f"\u2014 {c['Name']}")
    lines += ["", "All content is synthetic and generated from the demo model.",
              f"\u201c{BRAND}\u201d is a fictitious company; any resemblance to real "
              "organizations is coincidental."]
    return _w(out_dir, "README.md", "\n".join(lines))


def _conference_guide(out_dir, c, tables):
    cid = c["ConferenceId"]
    sessions = [s for s in tables["session"] if s["ConferenceId"] == cid]
    keynote = next((s for s in sessions if s["SessionType"] == "Keynote"), None)
    ss_map = {}
    for ss in tables["sessionspeaker"]:
        ss_map.setdefault(ss["SessionId"], []).append(ss["SpeakerId"])
    spk_name = {s["SpeakerId"]: s["FullName"] for s in tables["speaker"]}
    tracks = sorted({s["Track"] for s in sessions if s["Track"] != "Keynote"})

    lines = [
        f"# {c['Name']} \u2014 Conference Guide", "",
        f"**Theme:** {c['Theme']}  ",
        f"**Location:** {c['City']}  ",
        f"**Dates:** {c['StartDate']} to {c['EndDate']} ({c['Days']} days)  ",
        f"**Sessions:** {len(sessions)}", "",
        "## Overview", "",
        f"The {c['Name']} is {BRAND}'s flagship gathering for {c['Theme'].lower()} "
        "leaders and practitioners. Expect a mainstage keynote, deep-dive breakouts, "
        "hands-on workshops and peer roundtables, plus an expo of sponsoring "
        "technology providers.", "",
    ]
    if keynote:
        kspk = ", ".join(spk_name[i] for i in ss_map.get(keynote["SessionId"], []))
        lines += ["## Opening keynote", "",
                  f"**{keynote['Title']}** \u2014 delivered by {kspk} "
                  f"in {keynote['Room']}.", ""]
    lines += ["## Tracks", ""]
    lines += [f"- {t}" for t in tracks]
    lines += ["", "## Selected sessions", ""]
    for s in sessions[1:9]:
        who = ", ".join(spk_name[i] for i in ss_map.get(s["SessionId"], [])) or "TBA"
        lines.append(f"- **{s['Title']}** ({s['SessionType']}, {s['Track']}) "
                     f"\u2014 {who}")
    lines += ["", "## Who should attend", "",
              f"Leaders and specialists focused on {c['Theme'].lower()}, along with "
              "their platform, data and operations teams."]
    return _w(out_dir, f"conference-{cid}-guide.md", "\n".join(lines))


def _speaker_directory(out_dir, tables, manifest):
    top = manifest["top_speakers_by_licensed_users_attended"][0][0]
    spk = tables["speaker"]
    # sessions per speaker for context
    ss_count = {}
    for ss in tables["sessionspeaker"]:
        ss_count[ss["SpeakerId"]] = ss_count.get(ss["SpeakerId"], 0) + 1
    lines = [
        f"# {BRAND} Speaker Directory", "",
        f"This directory profiles the {len(spk)} speakers across the "
        f"{BRAND} conference series \u2014 {BRAND} analysts, industry guests, "
        "practitioners and solution-provider experts.", "",
        f"> **Most-attended speaker:** {top} consistently draws the largest "
        "licensed-user audiences across the series (see the Fabric data for exact "
        "figures).", "",
    ]
    for s in spk:
        lines += [
            f"## {s['FullName']}",
            f"*{s['Affiliation']} \u00b7 {s['Expertise']} \u00b7 "
            f"{s['YearsExperience']} years*", "",
            f"{s['FullName']} is a {'keynote speaker' if s['IsKeynote'] else 'session leader'} "
            f"specializing in {s['Expertise'].lower()}. With {s['YearsExperience']} "
            f"years of experience as a {s['Affiliation'].lower()}, "
            f"{s['FullName'].split()[0]} leads {ss_count.get(s['SpeakerId'],0)} "
            f"session(s) across the {BRAND} series, covering strategy, real-world "
            "case studies and hands-on guidance.", "",
        ]
    return _w(out_dir, "speaker-directory.md", "\n".join(lines))


def _sponsor_prospectus(out_dir, tables, manifest):
    top = manifest["top_sponsors_by_influenced_pipeline"][0][0]
    lines = [
        f"# {BRAND} Sponsorship Prospectus", "",
        f"{BRAND} conferences connect sponsoring technology providers with senior "
        "decision-makers across data, security, infrastructure, supply chain and "
        "marketing. This prospectus describes the available packages and the "
        "current sponsor roster.", "",
        "## Sponsorship packages", "",
        f"{BRAND} offers five sponsorship packages per event:", "",
    ]
    for tier, (price, benefits) in PACKAGE_BENEFITS.items():
        lines.append(f"### {tier} \u2014 {price} per event")
        lines += [f"- {b}" for b in benefits]
        lines.append("")
    lines += [
        "## Value and ROI", "",
        "Sponsors are measured on leads captured and qualified, influenced "
        "pipeline and closed-won revenue attributed to the event.", "",
        f"> **Top value driver:** {top} has generated the most influenced "
        "pipeline across the series (see the Fabric data for exact figures and "
        "ROI).", "",
        "## Sponsor roster", "",
    ]
    for s in tables["sponsor"]:
        lines.append(f"- **{s['Name']}** \u2014 {s['Industry']}")
    return _w(out_dir, "sponsor-prospectus.md", "\n".join(lines))


def _attendee_faq(out_dir):
    text = f"""# {BRAND} Attendee FAQ

## Registration and passes

**What pass types are available?**
Full-conference passes include all keynotes, breakouts, workshops and the expo.
Day passes cover a single day. Virtual passes provide live-streamed keynotes and
selected breakouts plus on-demand recordings.

**Can I transfer my registration?**
Yes. Registrations may be transferred to a colleague at no charge up to five
business days before the event.

## On-site

**When should I arrive?**
Registration and badge pickup open the afternoon before day one and from 7:30 AM
each conference day. Arrive early on keynote mornings \u2014 mainstage seating fills
quickly.

**Are meals included?**
Full and day passes include morning refreshments and lunch on attendance days.

## Virtual attendance

**How do I join virtually?**
Virtual attendees receive a personalized link. Keynotes stream live; most
breakouts are available on demand within 24 hours.

## Refunds

**What is the refund policy?**
Cancellations more than 30 days before the event receive a full refund less a
processing fee. Cancellations 8\u201330 days before receive a 50% refund.
Cancellations within 7 days are non-refundable but fully transferable.

## Continuing education

**Do sessions carry CPE credit?**
Most strategy and technical sessions qualify for continuing-education credit.
Scan in and out of each session to have credits recorded.
"""
    return _w(out_dir, "attendee-faq.md", text)


def _policies(out_dir):
    text = f"""# {BRAND} Policies and Guidelines

## Code of conduct

{BRAND} is committed to a harassment-free, inclusive experience for everyone.
All attendees, speakers, sponsors and staff are expected to treat one another
with respect. Unacceptable behavior may result in removal from the event without
refund.

## Recording and photography

Keynotes and most sessions are recorded by {BRAND} for on-demand access.
Attendees may take photos for personal use but may not record full sessions for
redistribution. Sponsors may not photograph or record attendees without consent.

## Data and privacy

Badge scans at sessions and sponsor booths are used to record attendance and,
where you opt in, to share your contact details with the scanning sponsor. You
can manage your sharing preferences in the event app. {BRAND} processes personal
data in line with its privacy notice and applicable data-protection law.

## Lead sharing

When you allow a sponsor to scan your badge, {BRAND} shares your registration
contact details with that sponsor for follow-up. You may opt out at any time.

## Health and safety

Follow venue and staff guidance at all times. Emergency exits and assembly
points are marked in each hall and listed in the event app.

## Intellectual property

Session content is the property of the presenting speaker or organization.
Slides are shared at the presenter's discretion after the event.
"""
    return _w(out_dir, "policies-and-guidelines.md", text)

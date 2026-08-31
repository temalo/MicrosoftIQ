"""
Deterministic synthetic-data model for the Contoso Events "Microsoft IQ" demo.

This module is the single source of truth. `build_model()` returns every table
as a list of dicts; `compute_manifest()` derives the headline answers. Both the
CSV exporter (tables.py) and the knowledge generator (knowledge.py) import this,
so the business data and the unstructured knowledge always agree.

Everything is seeded, so the demo is fully reproducible: the same top speaker,
the same top sponsor, and the same licensed-user definition spread every run.
"""

import random
from datetime import date, timedelta

SEED = 20260831

# --- Reference pools --------------------------------------------------------
FIRST_NAMES = [
    "Ava", "Liam", "Priya", "Mateo", "Sofia", "Noah", "Aisha", "Ethan", "Mia",
    "Omar", "Zoe", "Lucas", "Nina", "Kai", "Elena", "Arjun", "Clara", "Diego",
    "Hana", "Raj", "Lena", "Yusuf", "Grace", "Marco", "Ines", "Tariq", "Anna",
    "Pablo", "Rohan", "Maya", "Felix", "Sara", "Ivan", "Lucia", "Amir", "Nora",
    "Theo", "Ada", "Bruno", "Leila", "Sven", "Rosa", "Kenji", "Farah", "Otto",
    "Vera", "Hugo", "Dita", "Milan", "Iris",
]
LAST_NAMES = [
    "Kumar", "Silva", "Tanaka", "Schmidt", "Okafor", "Nguyen", "Rossi", "Haddad",
    "Andersson", "Costa", "Petrov", "Mbeki", "Larsen", "Reyes", "Novak", "Khan",
    "Moreau", "Fischer", "Santos", "Yilmaz", "Bauer", "Dubois", "Ali", "Weber",
    "Ivanov", "Suzuki", "Meyer", "Cohen", "Park", "Romano", "Jansen", "Marino",
    "Halonen", "Adeyemi", "Vargas", "Klein", "Sato", "Bianchi", "Popov", "Diallo",
]

BUSINESS_UNITS = [
    # (name, named_licensed, paid_seat, served, login_capable) cumulative targets
    "Sales", "Finance", "Global Service & Delivery", "Shared Services",
    "Research", "Product", "Marketing", "Operations",
]
ROLES = [
    "Analyst", "Manager", "Director", "Individual Contributor", "Executive",
    "Consultant", "Engineer", "Coordinator",
]
PRODUCTS = [
    "Research Portal", "Peer Community", "Advisory Hours", "Benchmark Suite",
    "Event Pass", "Insight Feed",
]
ENTITLEMENT_TIERS = ["Standard", "Professional", "Enterprise"]
ORG_SEGMENTS = ["Enterprise", "Commercial", "Public Sector", "SMB"]
ORG_PREFIX = [
    "Northwind", "Fabrikam", "Contoso", "Adventure", "Tailspin", "Wingtip",
    "Proseware", "Litware", "Fourth Coffee", "Graphic Design Inst.", "Coho",
    "Alpine Ski House", "Blue Yonder", "Trey Research", "Woodgrove", "Margie's",
    "Lucerne", "Nod Publishers", "First Up", "Relecloud",
]
ORG_SUFFIX = ["Group", "Holdings", "Industries", "Systems", "Partners", "Corp",
              "Labs", "Global", "Networks", "Solutions"]

# 8 flagship conferences (generic, non-branded)
CONFERENCES = [
    ("Data & Analytics Summit", "Analytics & AI", "Orlando", 4),
    ("IT Infrastructure & Operations Summit", "Infrastructure", "Las Vegas", 3),
    ("Security & Risk Summit", "Security", "National Harbor", 3),
    ("Supply Chain Symposium", "Supply Chain", "Barcelona", 3),
    ("Marketing & CX Conference", "Marketing", "Denver", 2),
    ("CIO Leadership Forum", "Executive Leadership", "Phoenix", 2),
    ("Application Innovation Summit", "Software Engineering", "Toronto", 3),
    ("Digital Workplace Summit", "Employee Experience", "Amsterdam", 2),
]
# relative registration weight per conference (index 0 = flagship, largest)
CONF_WEIGHT = [1.00, 0.78, 0.72, 0.60, 0.50, 0.42, 0.55, 0.40]

TRACKS = ["Keynote", "Strategy", "Technical Deep Dive", "Case Study",
          "Workshop", "Roundtable", "Emerging Tech"]
SESSION_TYPES = ["Keynote", "Breakout", "Workshop", "Roundtable"]

# 30 fictitious sponsor companies (index 0 = headline value driver)
SPONSORS = [
    ("Datallar", "Data Governance"), ("Corvexa", "Analytics Platform"),
    ("Monteclar", "Data Observability"), ("Snowpeak", "Cloud Data Warehouse"),
    ("Alteris", "Data Prep"), ("Verithex", "Master Data"),
    ("Quantahub", "ML Ops"), ("Streamlio", "Streaming"),
    ("Nimbra", "Cloud Infra"), ("Cryptonode", "Security"),
    ("Sentinela", "Threat Detection"), ("Identra", "Identity"),
    ("Fluxgate", "Integration"), ("Cargowise", "Supply Chain"),
    ("Logithread", "Logistics"), ("Palisade", "Risk & GRC"),
    ("Mercatis", "MarTech"), ("Personyx", "CX / CDP"),
    ("Cognita", "AI Assistants"), ("Vectorly", "Vector Search"),
    ("Brightpath", "BI"), ("Cloudmason", "FinOps"),
    ("Orchestrix", "Workflow"), ("Kubernaut", "Containers"),
    ("Devanti", "DevEx"), ("Warehowl", "Data Lakehouse"),
    ("Metricly", "Metrics"), ("Consenta", "Privacy"),
    ("Bindery", "API Management"), ("Optivance", "Optimization"),
]
SPONSOR_TIERS = [("Platinum", 250000), ("Gold", 120000),
                 ("Silver", 55000), ("Bronze", 22000), ("Startup", 8000)]

N_USERS = 5000
N_SPEAKERS = 60
N_REGISTRATIONS_TARGET = 30000

# Licensed-user definition targets (the "one question, four answers" story)
DEFINITION_TARGETS = {
    "NamedLicensedUser": 658,       # Sales — named licensed user
    "PaidLicensedSeat": 749,        # Finance — paid licensed seat
    "ServedPopulation": 2294,       # Global Service & Delivery — served population
    "LoginCapableIdentity": 3484,   # Shared Services — login-capable identity
}


def _iso(d):
    return d.isoformat()


def build_model():
    rng = random.Random(SEED)
    tables = {}

    # ---- dimensions --------------------------------------------------------
    businessunit = [{"BusinessUnitId": i + 1, "Name": n}
                    for i, n in enumerate(BUSINESS_UNITS)]
    role = [{"RoleId": i + 1, "Name": n} for i, n in enumerate(ROLES)]
    product = [{"ProductId": i + 1, "Name": n} for i, n in enumerate(PRODUCTS)]

    entitlement = []
    eid = 1
    for p in product:
        for tier in ENTITLEMENT_TIERS:
            entitlement.append({
                "EntitlementId": eid, "ProductId": p["ProductId"],
                "Name": f'{p["Name"]} \u2013 {tier}', "Tier": tier,
            })
            eid += 1

    N_ORGS = 220
    org = []
    for i in range(N_ORGS):
        pref = ORG_PREFIX[i % len(ORG_PREFIX)]
        suf = ORG_SUFFIX[(i // len(ORG_PREFIX)) % len(ORG_SUFFIX)]
        org.append({
            "OrgId": i + 1,
            "Name": f"{pref} {suf}" + ("" if i < len(ORG_PREFIX) else f" {i//len(ORG_PREFIX)+1}"),
            "Segment": ORG_SEGMENTS[i % len(ORG_SEGMENTS)],
        })

    tables["businessunit"] = businessunit
    tables["role"] = role
    tables["product"] = product
    tables["entitlement"] = entitlement
    tables["org"] = org

    # ---- users -------------------------------------------------------------
    # Nested definition flags so the four "licensed user" answers are exactly
    # 658 / 749 / 2294 / 3484 across the 5,000 distinct users.
    order = list(range(N_USERS))
    rng.shuffle(order)
    named = set(order[:DEFINITION_TARGETS["NamedLicensedUser"]])
    paid = set(order[:DEFINITION_TARGETS["PaidLicensedSeat"]])
    served = set(order[:DEFINITION_TARGETS["ServedPopulation"]])
    login = set(order[:DEFINITION_TARGETS["LoginCapableIdentity"]])

    users = []
    for uid in range(1, N_USERS + 1):
        idx = uid - 1
        fn = rng.choice(FIRST_NAMES)
        ln = rng.choice(LAST_NAMES)
        users.append({
            "UserId": uid,
            "FullName": f"{fn} {ln}",
            "Email": f"{fn.lower()}.{ln.lower().replace(chr(39),'').replace('.','').replace(' ','')}{uid}@example.com",
            "BusinessUnitId": rng.randint(1, len(businessunit)),
            "RoleId": rng.randint(1, len(role)),
            "OrgId": rng.randint(1, N_ORGS),
            "PrimaryProductId": rng.randint(1, len(product)),
            "NamedLicensedUser": int(idx in named),
            "PaidLicensedSeat": int(idx in paid),
            "ServedPopulation": int(idx in served),
            "LoginCapableIdentity": int(idx in login),
        })
    tables["user"] = users

    # ---- licences (User has Licence; Licence belongs to Org) ---------------
    # ~90% of users hold at least one active licence -> canonical "licensed".
    userlicence = []
    lid = 1
    licensed_users = set()
    base_day = date(2025, 1, 1)
    for u in users:
        if rng.random() < 0.90:
            n_lic = rng.choices([1, 2, 3], weights=[70, 22, 8])[0]
            for _ in range(n_lic):
                pid = rng.randint(1, len(product))
                ent = rng.choice([e for e in entitlement if e["ProductId"] == pid])
                status = "Active" if rng.random() < 0.93 else "Expired"
                start = base_day - timedelta(days=rng.randint(30, 700))
                userlicence.append({
                    "UserLicenceId": lid,
                    "UserId": u["UserId"],
                    "ProductId": pid,
                    "EntitlementId": ent["EntitlementId"],
                    "OrgId": u["OrgId"],
                    "Status": status,
                    "StartDate": _iso(start),
                    "EndDate": _iso(start + timedelta(days=365)),
                })
                lid += 1
                if status == "Active":
                    licensed_users.add(u["UserId"])
    tables["userlicence"] = userlicence

    # ---- conferences -------------------------------------------------------
    conference = []
    conf_dates = []
    for i, (name, theme, city, days) in enumerate(CONFERENCES):
        start = date(2026, 2, 1) + timedelta(days=i * 32)
        conference.append({
            "ConferenceId": i + 1, "Name": name, "Theme": theme,
            "City": city, "StartDate": _iso(start),
            "EndDate": _iso(start + timedelta(days=days - 1)), "Days": days,
        })
        conf_dates.append(start)
    tables["conference"] = conference

    # ---- speakers ----------------------------------------------------------
    EXPERTISE = ["Data & Analytics", "AI & Machine Learning", "Cybersecurity",
                 "Cloud Infrastructure", "Supply Chain", "Marketing & CX",
                 "Executive Strategy", "Software Engineering",
                 "Data Governance", "FinOps"]
    ORGS_SPK = ["Contoso Events (Analyst)", "Industry Guest", "Solution Provider",
                "Academic", "Practitioner"]
    speakers = []
    used_names = set()
    for sid in range(1, N_SPEAKERS + 1):
        while True:
            fn = rng.choice(FIRST_NAMES)
            ln = rng.choice(LAST_NAMES)
            nm = f"{fn} {ln}"
            if nm not in used_names:
                used_names.add(nm)
                break
        speakers.append({
            "SpeakerId": sid,
            "FullName": nm,
            "Affiliation": ORGS_SPK[(sid - 1) % len(ORGS_SPK)],
            "Expertise": EXPERTISE[(sid - 1) % len(EXPERTISE)],
            "YearsExperience": rng.randint(6, 28),
            "IsKeynote": int(sid <= 12),
        })
    tables["speaker"] = speakers

    # ---- sessions + session-speaker bridge ---------------------------------
    session = []
    sessionspeaker = []
    ssid = 1
    sid_seq = 1
    conf_sessions = {c["ConferenceId"]: [] for c in conference}
    for c in conference:
        cid = c["ConferenceId"]
        n_sessions = {1: 22, 2: 18, 3: 18, 4: 16, 5: 14, 6: 12, 7: 16, 8: 12}[cid]
        for k in range(n_sessions):
            is_keynote = k == 0
            stype = "Keynote" if is_keynote else rng.choices(
                ["Breakout", "Workshop", "Roundtable"], weights=[64, 22, 14])[0]
            track = "Keynote" if is_keynote else rng.choice(TRACKS[1:])
            start = conf_dates[cid - 1] + timedelta(
                days=rng.randint(0, c["Days"] - 1),
                hours=rng.choice([9, 11, 13, 15]))
            session.append({
                "SessionId": sid_seq,
                "ConferenceId": cid,
                "Title": _session_title(rng, c["Theme"], track, is_keynote),
                "Track": track,
                "SessionType": stype,
                "Room": f"Hall {rng.choice('ABCDE')}" if is_keynote else f"Room {rng.randint(101,240)}",
                "StartTime": start.isoformat(),
                "CapacityHint": {"Keynote": 5000, "Breakout": 400,
                                 "Workshop": 80, "Roundtable": 30}[stype],
            })
            conf_sessions[cid].append(sid_seq)

            # assign speakers: keynote of the two flagship confs -> speaker 1
            if is_keynote and cid in (1, 2):
                spk_ids = [1]
            elif is_keynote:
                spk_ids = [rng.randint(2, 12)]
            else:
                spk_ids = rng.sample(range(1, N_SPEAKERS + 1),
                                     rng.choices([1, 2], weights=[70, 30])[0])
            for role_i, sp in enumerate(spk_ids):
                sessionspeaker.append({
                    "SessionSpeakerId": ssid, "SessionId": sid_seq,
                    "SpeakerId": sp,
                    "Role": "Presenter" if role_i == 0 else "Co-presenter",
                })
                ssid += 1
            sid_seq += 1
    tables["session"] = session
    tables["sessionspeaker"] = sessionspeaker

    # ---- registrations -----------------------------------------------------
    # Each conference draws a weighted subset of the 5,000-user pool.
    registration = []
    rid = 1
    conf_registrants = {}
    for c in conference:
        cid = c["ConferenceId"]
        share = CONF_WEIGHT[cid - 1]
        n_reg = int(N_USERS * share * 0.98)
        regs = rng.sample(range(1, N_USERS + 1), n_reg)
        conf_registrants[cid] = regs
        for uid in regs:
            registration.append({
                "RegistrationId": rid, "ConferenceId": cid, "UserId": uid,
                "RegType": rng.choices(["Full", "Day Pass", "Virtual"],
                                       weights=[68, 18, 14])[0],
                "Status": "Attended" if rng.random() < 0.9 else "Registered",
            })
            rid += 1
    tables["registration"] = registration

    # ---- session attendance ------------------------------------------------
    # Popularity by session type drives how many of a conference's registrants
    # show up. Keynotes pull the crowd -> the flagship keynoter tops the chart.
    attendance = []
    aid = 1
    pop = {"Keynote": 0.86, "Breakout": 0.16, "Workshop": 0.05, "Roundtable": 0.02}
    sess_by_id = {s["SessionId"]: s for s in session}
    for cid, regs in conf_registrants.items():
        for sess_id in conf_sessions[cid]:
            s = sess_by_id[sess_id]
            frac = pop[s["SessionType"]] * rng.uniform(0.85, 1.15)
            frac = min(frac, 0.95)
            n = int(len(regs) * frac)
            for uid in rng.sample(regs, n):
                attendance.append({
                    "SessionAttendanceId": aid, "SessionId": sess_id,
                    "ConferenceId": cid, "UserId": uid,
                    "DwellMinutes": rng.randint(8, 60),
                    "CheckIn": "Badge" if rng.random() < 0.8 else "App",
                })
                aid += 1
    tables["sessionattendance"] = attendance

    # ---- sponsors + conference-sponsor value -------------------------------
    sponsor = []
    for i, (name, industry) in enumerate(SPONSORS):
        sponsor.append({"SponsorId": i + 1, "Name": name, "Industry": industry})
    tables["sponsor"] = sponsor

    conferencesponsor = []
    csid = 1
    for c in conference:
        cid = c["ConferenceId"]
        n_sp = rng.randint(9, 14)
        chosen = set(rng.sample(range(2, len(SPONSORS) + 1), n_sp))
        chosen.add(1)  # the headline value driver sponsors every conference
        for sp in sorted(chosen):
            if sp == 1:
                tier_name, fee = "Platinum", 250000
                mult = rng.uniform(2.4, 2.9)
            else:
                tier_name, fee = rng.choices(SPONSOR_TIERS,
                                             weights=[10, 20, 30, 25, 15])[0]
                mult = rng.uniform(1.8, 3.0)
            leads = int(fee / 1000 * rng.uniform(0.8, 1.4))
            qualified = int(leads * rng.uniform(0.35, 0.55))
            influenced = round(fee * mult, 2)
            closed = round(influenced * rng.uniform(0.12, 0.22), 2)
            conferencesponsor.append({
                "ConferenceSponsorId": csid, "ConferenceId": cid, "SponsorId": sp,
                "Tier": tier_name, "SponsorshipFeeUSD": fee,
                "LeadsCaptured": leads, "LeadsQualified": qualified,
                "InfluencedPipelineUSD": influenced, "ClosedWonUSD": closed,
            })
            csid += 1
    tables["conferencesponsor"] = conferencesponsor

    # ---- session feedback --------------------------------------------------
    feedback = []
    fid = 1
    for s in session:
        n_fb = {"Keynote": 400, "Breakout": 90, "Workshop": 40,
                "Roundtable": 18}[s["SessionType"]]
        for _ in range(int(n_fb * rng.uniform(0.6, 1.0))):
            feedback.append({
                "SessionFeedbackId": fid, "SessionId": s["SessionId"],
                "ConferenceId": s["ConferenceId"],
                "Rating": rng.choices([5, 4, 3, 2, 1],
                                      weights=[46, 34, 13, 5, 2])[0],
                "NPS": rng.randint(-100, 100),
            })
            fid += 1
    tables["sessionfeedback"] = feedback

    # ---- conference finance ------------------------------------------------
    conferencefinance = []
    for c in conference:
        cid = c["ConferenceId"]
        regs = len(conf_registrants[cid])
        revenue = round(regs * rng.uniform(1400, 2200)
                        + sum(cs["SponsorshipFeeUSD"] for cs in conferencesponsor
                              if cs["ConferenceId"] == cid), 2)
        cost = round(revenue * rng.uniform(0.45, 0.62), 2)
        conferencefinance.append({
            "ConferenceFinanceId": cid, "ConferenceId": cid,
            "RegistrationRevenueUSD": round(revenue * 0.6, 2),
            "SponsorRevenueUSD": round(revenue * 0.4, 2),
            "TotalRevenueUSD": revenue, "TotalCostUSD": cost,
            "MarginUSD": round(revenue - cost, 2),
        })
    tables["conferencefinance"] = conferencefinance

    return tables


def _session_title(rng, theme, track, is_keynote):
    if is_keynote:
        openers = ["Opening Keynote", "Executive Keynote", "Vision Keynote"]
        return f"{rng.choice(openers)}: The Future of {theme}"
    verbs = ["Scaling", "Modernizing", "Governing", "Operationalizing",
             "Rethinking", "Accelerating", "Securing", "Measuring"]
    nouns = ["Your Data Estate", "the AI Lifecycle", "Cloud Costs",
             "Customer Journeys", "the Supply Chain", "Platform Teams",
             "Zero-Trust", "Analytics at Scale", "Governance", "Developer Velocity"]
    return f"{rng.choice(verbs)} {rng.choice(nouns)} ({track})"


def compute_manifest(tables):
    """Derive the headline answers so data, knowledge and slides agree."""
    active_licensed = set()
    for ul in tables["userlicence"]:
        if ul["Status"] == "Active":
            active_licensed.add(ul["UserId"])

    # speaker -> distinct licensed attendees
    sess_speakers = {}
    for ss in tables["sessionspeaker"]:
        sess_speakers.setdefault(ss["SessionId"], []).append(ss["SpeakerId"])
    spk_users = {}
    for a in tables["sessionattendance"]:
        if a["UserId"] in active_licensed:
            for sp in sess_speakers.get(a["SessionId"], []):
                spk_users.setdefault(sp, set()).add(a["UserId"])
    spk_name = {s["SpeakerId"]: s["FullName"] for s in tables["speaker"]}
    top_speakers = sorted(((spk_name[k], len(v)) for k, v in spk_users.items()),
                          key=lambda x: -x[1])[:5]

    # sponsor -> influenced pipeline
    sp_val = {}
    for cs in tables["conferencesponsor"]:
        sp_val.setdefault(cs["SponsorId"], {"pipe": 0.0, "closed": 0.0, "fee": 0})
        sp_val[cs["SponsorId"]]["pipe"] += cs["InfluencedPipelineUSD"]
        sp_val[cs["SponsorId"]]["closed"] += cs["ClosedWonUSD"]
        sp_val[cs["SponsorId"]]["fee"] += cs["SponsorshipFeeUSD"]
    sp_name = {s["SponsorId"]: s["Name"] for s in tables["sponsor"]}
    top_sponsors = sorted(
        ((sp_name[k], round(v["pipe"], 2), round(v["pipe"] / v["fee"], 2))
         for k, v in sp_val.items()),
        key=lambda x: -x[1])[:5]

    definitions = {k: sum(u[k] for u in tables["user"])
                   for k in DEFINITION_TARGETS}

    return {
        "top_speakers_by_licensed_users_attended": top_speakers,
        "top_sponsors_by_influenced_pipeline": top_sponsors,
        "licensed_user_definitions": definitions,
        "distinct_active_licensed_users": len(active_licensed),
        "row_counts": {k: len(v) for k, v in tables.items()},
    }

"""Full-year content calendar: which moments fall in which weeks, and what the 3-a-day plan looks like."""
import datetime as dt

from . import moments as mom
from .util import cfg, today_local


def year_calendar(year=None):
    year = year or today_local().year
    rows = []
    for m in cfg("moments"):
        for start, end in mom.windows(m, year):
            if start.year == year or end.year == year:
                lead = dt.timedelta(days=m.get("lead_days", 0))
                rows.append({"id": m["id"], "name": m["name"], "start": start.isoformat(), "end": end.isoformat(),
                             "posting_from": (start - lead).isoformat(), "priority": m.get("priority", 1),
                             "campaign": bool(m.get("campaign")), "approx": bool(m.get("approx")),
                             "regions": m.get("regions", ["all"])})
    rows.sort(key=lambda r: r["start"])
    return rows


def as_markdown(year=None):
    out = ["| Starts | Ends | Moment | Post from | Regions | Notes |", "|---|---|---|---|---|---|"]
    for r in year_calendar(year):
        notes = ", ".join(x for x in ["campaign" if r["campaign"] else "", "check dates" if r["approx"] else ""] if x)
        out.append(f"| {r['start']} | {r['end']} | {r['name']} | {r['posting_from']} | {', '.join(r['regions'])} | {notes} |")
    return "\n".join(out)

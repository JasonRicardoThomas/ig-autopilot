"""Events and seasonal moments: date windows, lead days, region filter."""
import datetime as dt

from .util import cfg


def _nth_weekday(year, month, weekday, n):
    first = dt.date(year, month, 1)
    return first + dt.timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def windows(moment, year):
    """All (start, end) windows of a moment for the given year."""
    out = []
    if "dates" in moment:
        for s, e in moment["dates"]:
            out.append((dt.date.fromisoformat(s), dt.date.fromisoformat(e)))
    elif "rule" in moment:
        r = moment["rule"]
        d = _nth_weekday(year, r["month"], r["weekday"], r["n"])
        out.append((d - dt.timedelta(days=r.get("before", 0)), d + dt.timedelta(days=r.get("after", 0))))
    else:
        sm, sd = map(int, moment["start"].split("-"))
        em, ed = map(int, moment["end"].split("-"))
        start = dt.date(year, sm, sd)
        end_year = year + 1 if (em, ed) < (sm, sd) else year
        out.append((start, dt.date(end_year, em, ed)))
    return out


def active_window(moment, today):
    """The window (start, end) that is active (including lead days) on `today`, or None."""
    lead = dt.timedelta(days=moment.get("lead_days", 0))
    for year in (today.year - 1, today.year, today.year + 1):
        for start, end in windows(moment, year):
            if start - lead <= today <= end:
                return start, end
    return None


def region_ok(moment, region):
    regs = moment.get("regions", ["all"])
    return "all" in regs or region in regs


def active_moments(today, region=None):
    """Active moments sorted by priority (high first), then nearest start."""
    found = []
    for m in cfg("moments"):
        w = active_window(m, today)
        if w and (region is None or region_ok(m, region)):
            found.append((m, w))
    found.sort(key=lambda mw: (-mw[0].get("priority", 1), abs((mw[1][0] - today).days)))
    return found


def occurrence_key(moment, window):
    return f"{moment['id']}:{window[0].isoformat()}"

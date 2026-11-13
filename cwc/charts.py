"""Charts as self-contained SVG strings, drawn from the findings dictionary only.

Every chart function returns {"id", "svg", "alt", "columns", "rows"}: the picture,
a text alternative, and the same data as a table. The SVG carries its own styles
and background, so the same string works inside the dashboard page and as a
separate image file that GitHub can show. Marks that can be pointed at carry a
`data-tip` attribute; the dashboard turns it into a hover read-out.

Colour roles (fixed across charts)
  crimson  NEAR Intents, or the part of its revenue the thesis is about
  blue     the comparison: the peer basket, or the other part of revenue
  taupe    context that is shown but is not the subject
"""
from __future__ import annotations

import datetime as dt
import html
import math

W = 960
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
SURFACE = "#FBF6EA"
INK = "#2E0B13"
INK2 = "#5E4A44"
MUTED = "#7A695D"
GRID = "#E9DFCB"
AXIS = "#CDBFA6"
CRIMSON = "#A8142D"
BLUE = "#1D6996"
TAUPE = "#A89B86"
BURGUNDY = "#4A0E1C"
TINT = "#F1DAD6"
BAND = "#F1E8D3"

STYLE = (
    f"text{{font-family:{FONT};font-size:13px;fill:{INK2}}}"
    f".s{{font-size:12px;fill:{MUTED}}}"
    f".b{{font-weight:600;fill:{INK}}}"
    f".n{{font-variant-numeric:tabular-nums}}"
    f".h{{paint-order:stroke;stroke:{SURFACE};stroke-width:5px;stroke-linejoin:round}}"
    ".hit{fill:transparent;stroke:none}"
)

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def num(value: float, digits: int = 1) -> str:
    text = f"{value:.{digits}f}"
    return text[1:] if text.startswith("-") and float(text) == 0 else text


def pct(value: float, digits: int = 1, sign: bool = False) -> str:
    text = num(value, digits)
    if sign and not text.startswith("-") and float(text) != 0:
        text = "+" + text
    return text.replace("-", "−") + "%"


def usd_m(value: float, digits: int = 1) -> str:
    return "$" + num(value / 1e6, digits) + "M"


def usd_k(value: float, digits: int = 1) -> str:
    return "$" + num(value / 1e3, digits) + "K"


def day_label(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def c(value: float) -> str:
    return f"{value:.1f}"


class Canvas:
    def __init__(self, height: int, chart_id: str, title: str, desc: str):
        self.h = height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" width="{W}" height="{height}" '
            f'role="img" aria-labelledby="{chart_id}-t {chart_id}-d" class="chart" id="{chart_id}">',
            f'<title id="{chart_id}-t">{esc(title)}</title><desc id="{chart_id}-d">{esc(desc)}</desc>',
            f"<style>{STYLE}</style>",
            f'<rect width="{W}" height="{height}" fill="{SURFACE}"/>',
        ]

    def add(self, fragment: str) -> None:
        self.parts.append(fragment)

    def line(self, x1, y1, x2, y2, stroke=GRID, width=1.0, dash=None) -> None:
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<line x1="{c(x1)}" y1="{c(y1)}" x2="{c(x2)}" y2="{c(y2)}" stroke="{stroke}" stroke-width="{width}"{extra}/>')

    def rect(self, x, y, w, h, fill, rx=0.0, extra="") -> None:
        self.add(f'<rect x="{c(x)}" y="{c(y)}" width="{c(max(w, 0))}" height="{c(max(h, 0))}" fill="{fill}" rx="{c(rx)}"{extra}/>')

    def text(self, x, y, value, anchor="start", cls="", extra="") -> None:
        klass = f' class="{cls}"' if cls else ""
        self.add(f'<text x="{c(x)}" y="{c(y)}" text-anchor="{anchor}"{klass}{extra}>{esc(value)}</text>')

    def label(self, x, y, value, cls="b n") -> None:
        """A centred label on a small patch of the surface colour, so it stays readable on top of a line."""
        width = 7.6 * len(str(value)) + 10
        self.rect(x - width / 2, y - 13, width, 18, SURFACE, 3)
        self.text(x, y, value, "middle", cls)

    def dot(self, x, y, r, fill) -> None:
        self.add(f'<circle cx="{c(x)}" cy="{c(y)}" r="{c(r)}" fill="{fill}" stroke="{SURFACE}" stroke-width="2"/>')

    def polyline(self, points, stroke, width=2.0) -> None:
        path = " ".join(f"{c(x)},{c(y)}" for x, y in points)
        self.add(f'<polyline points="{path}" fill="none" stroke="{stroke}" stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"/>')

    def bar_up(self, x, y_top, w, y_base, fill, round_top=True) -> None:
        """A vertical bar from the baseline up to y_top, with a rounded data end."""
        h = y_base - y_top
        if h <= 0.05:
            return
        r = min(4.0, w / 2.0, h) if round_top else 0.0
        self.add(f'<path d="M{c(x)},{c(y_base)} V{c(y_top + r)} Q{c(x)},{c(y_top)} {c(x + r)},{c(y_top)} H{c(x + w - r)} '
                 f'Q{c(x + w)},{c(y_top)} {c(x + w)},{c(y_top + r)} V{c(y_base)} Z" fill="{fill}"/>')

    def bar_signed(self, x, y_zero, w, y_value, fill) -> None:
        """A vertical bar from the zero line to y_value (above or below), rounded at the data end."""
        if abs(y_value - y_zero) <= 0.05:
            return
        r = min(4.0, w / 2.0, abs(y_value - y_zero))
        if y_value < y_zero:
            self.bar_up(x, y_value, w, y_zero, fill)
        else:
            self.add(f'<path d="M{c(x)},{c(y_zero)} V{c(y_value - r)} Q{c(x)},{c(y_value)} {c(x + r)},{c(y_value)} H{c(x + w - r)} '
                     f'Q{c(x + w)},{c(y_value)} {c(x + w)},{c(y_value - r)} V{c(y_zero)} Z" fill="{fill}"/>')

    def hit(self, x, y, w, h, tip: str) -> None:
        self.add(f'<rect class="hit" x="{c(x)}" y="{c(y)}" width="{c(max(w, 0))}" height="{c(max(h, 0))}" data-tip="{esc(tip)}" tabindex="-1"/>')

    def svg(self) -> str:
        return "".join(self.parts) + "</svg>"


def linear(d0: float, d1: float, r0: float, r1: float):
    span = (d1 - d0) or 1.0
    return lambda v: r0 + (v - d0) * (r1 - r0) / span


def ticks(lo: float, hi: float, step: float) -> list:
    out, k = [], math.ceil(lo / step - 1e-9)
    while k * step <= hi + 1e-9:
        out.append(k * step)
        k += 1
    return out


def clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def month_ticks(c_: Canvas, weeks: list, x_of, y: float) -> None:
    """Month names under a weekly x axis, at the first week that starts in each month."""
    seen = None
    for i, iso in enumerate(weeks):
        d = dt.date.fromisoformat(iso)
        if (d.year, d.month) != seen and d.day <= 7:
            seen = (d.year, d.month)
            label = MONTHS[d.month - 1] + (f" {d.year}" if d.month == 1 or i == 0 else "")
            c_.line(x_of(i), y, x_of(i), y + 5, AXIS)
            c_.text(x_of(i), y + 19, label, "start", "s")


def event_marker(c_: Canvas, x: float, y0: float, y1: float, label: str, anchor="start") -> None:
    c_.line(x, y0, x, y1, BURGUNDY, 1.5)
    c_.text(x + (6 if anchor == "start" else -6), y0 + 12, label, anchor, "b")


def legend(c_: Canvas, x: float, y: float, items: list) -> None:
    for label, colour in items:
        c_.rect(x, y - 9, 12, 12, colour, 3)
        c_.text(x + 18, y + 1, label)
        x += 30 + 7.0 * len(label)


# --------------------------------------------------------------------------- 1

def ruler(f: dict) -> dict:
    """The verdict in one picture: where the volume change can be, against the break-even loss."""
    et = f["event_test"]
    names = {"sc": "Synthetic control", "equal": "Equal-weight difference", "pooled": "Pooled-volume difference"}
    be = et["break_even_pct"]
    band = f["verdict"]["strict_band_pct"]
    lo_axis, hi_axis = -50.0, 70.0
    left, right, top, bottom = 250, W - 28, 58, 232
    cv = Canvas(286, "chart-ruler", "Volume change against peers after the fee switch, with the break-even loss",
                "Three estimates with 90 percent intervals on one axis, the break-even loss and the 15 percent line.")
    x = linear(lo_axis, hi_axis, left, right)
    cv.rect(x(lo_axis), top, x(clip(be, lo_axis, hi_axis)) - x(lo_axis), bottom - top, TINT)
    cv.rect(x(-band), top, x(0) - x(-band), bottom - top, BAND)
    for t in ticks(lo_axis, hi_axis, 10):
        cv.line(x(t), top, x(t), bottom, GRID)
        if t % 20 == 0:
            cv.text(x(t), bottom + 18, pct(t, 0, sign=True), "middle", "s n")
    cv.line(x(0), top - 6, x(0), bottom, INK2, 1.2)
    cv.text(x(0) + 5, top - 10, "no change", "start", "s")
    cv.line(x(be), top - 6, x(be), bottom, BURGUNDY, 2)
    cv.text(x(be) + 6, top - 26, f"break-even {pct(be)}", "start", "b n")
    cv.text(x(be) + 6, top - 10, "gain cancelled left of this line", "start", "s")
    cv.line(x(-band), top, x(-band), bottom, AXIS, 1.2)
    cv.text(x(-band) + 5, bottom - 8, f"{pct(-band, 0)} line", "start", "s n")
    rows = []
    for i, mode in enumerate(("sc", "equal", "pooled")):
        res = et["estimators"][mode]
        iv = res["interval"]
        y = top + 34 + i * 56
        colour, thick, r = (CRIMSON, 7.0, 7.0) if mode == "sc" else (TAUPE, 5.0, 5.5)
        cv.text(24, y - 3, names[mode], "start", "b")
        est = res["estimate_pct"]
        if iv["determined"]:
            a, b = clip(iv["lo_pct"], lo_axis, hi_axis), clip(iv["hi_pct"], lo_axis, hi_axis)
            cv.add(f'<line x1="{c(x(a))}" y1="{c(y)}" x2="{c(x(b))}" y2="{c(y)}" stroke="{colour}" stroke-width="{thick}" stroke-linecap="round"/>')
            cv.text(24, y + 15, f"{pct(est, 1, True)}  ({pct(iv['lo_pct'], 1, True)} to {pct(iv['hi_pct'], 1, True)})", "start", "s n")
            tip = f"{names[mode]}: {pct(est, 1, True)}, 90% interval {pct(iv['lo_pct'], 1, True)} to {pct(iv['hi_pct'], 1, True)}"
        else:
            cv.text(24, y + 15, f"{pct(est, 1, True)}  (interval not determined)", "start", "s n")
            tip = f"{names[mode]}: {pct(est, 1, True)}, interval not determined"
        cv.dot(x(clip(est, lo_axis, hi_axis)), y, r, colour)
        cv.hit(left, y - 20, right - left, 40, tip)
        rows.append([names[mode], pct(est, 1, True), pct(iv["lo_pct"], 1, True) if iv["determined"] else "n/a",
                     pct(iv["hi_pct"], 1, True) if iv["determined"] else "n/a", num(res["pre_rmse_log"], 3)])
    cv.text(left, bottom + 40, "Change in NEAR Intents weekly volume against its peers, 11 weeks after against 13 weeks before", "start", "s")
    return {"id": "ruler", "svg": cv.svg(),
            "alt": "Volume change against peers with 90 percent intervals for three estimators, the break-even loss and the 15 percent line.",
            "columns": ["Estimator", "Estimate", "Interval low", "Interval high", "Fit error before (log points)"], "rows": rows}


# --------------------------------------------------------------------------- 2

def capture(f: dict) -> dict:
    """Weekly capture, split into the two sources DefiLlama labels."""
    weeks = f["series"]["weekly"]
    n = len(weeks)
    left, right, top, bottom = 56, W - 20, 30, 300
    cv = Canvas(346, "chart-capture", "Share of gross fees that reached NEAR, by week and by source",
                "Stacked weekly bars: NEAR's share of partner fees and other revenue, and revenue from its own front end.")
    top_value = max(w["capture_earned"] for w in weeks) * 100
    y_max = 10 * math.ceil((top_value + 2) / 10)
    y = linear(0, y_max, bottom, top)
    step = (right - left) / n
    bar = min(22.0, step - 2.5)
    x_of = lambda i: left + i * step
    for t in ticks(0, y_max, 10):
        cv.line(left, y(t), right, y(t), GRID)
        cv.text(left - 8, y(t) + 4, pct(t, 0), "end", "s n")
    cv.line(left, bottom, right, bottom, AXIS)
    month_ticks(cv, [w["week"] for w in weeks], x_of, bottom)
    rows = []
    for i, w in enumerate(weeks):
        other, front = w["capture_other"] * 100, w["capture_earned_front_end"] * 100
        x0 = x_of(i) + (step - bar) / 2
        y_other = y(other)
        if front > 0.05:
            cv.bar_up(x0, y_other, bar, bottom, CRIMSON, round_top=False)
            cv.bar_up(x0, y(other + front), bar, y_other - 2 if other > 0.05 else bottom, BLUE)
        else:
            cv.bar_up(x0, y_other, bar, bottom, CRIMSON)
        tip = f"Week of {day_label(w['week'])}: {pct(other + front)} of fees ({pct(other)} partner fees and other, {pct(front)} own front end)"
        cv.hit(x_of(i), top, step, bottom - top, tip)
        rows.append([w["week"], pct(other, 2), pct(front, 2), pct(other + front, 2)])
    ev = [i for i, w in enumerate(weeks) if w["week"] == f["meta"]["event_date"]]
    if ev:
        event_marker(cv, x_of(ev[0]), top - 8, bottom, f"fee switch, {day_label(f['meta']['event_date'])}")
    legend(cv, left, bottom + 38, [("NEAR's share of partner fees, and other revenue", CRIMSON), ("NEAR's own front end", BLUE)])
    return {"id": "capture", "svg": cv.svg(), "alt": "Weekly share of gross fees that reached NEAR, split by source.",
            "columns": ["Week starting", "Partner fees and other", "Own front end", "Total"], "rows": rows}


# --------------------------------------------------------------------------- 3

def fee_rate(f: dict) -> dict:
    """The fee users pay, by week: did partner apps pass the cost on?"""
    weeks = f["series"]["weekly"]
    n = len(weeks)
    left, right, top, bottom = 56, W - 20, 26, 230
    cv = Canvas(270, "chart-fee", "Fees users pay per dollar swapped, by week",
                "Line of weekly gross fees divided by weekly volume, in basis points, with the average of each window.")
    y_max = 5 * math.ceil((max(w["fee_rate_bps"] for w in weeks) + 1) / 5)
    y = linear(0, y_max, bottom, top)
    step = (right - left) / n
    x_of = lambda i: left + i * step
    xm = lambda i: x_of(i) + step / 2
    for t in ticks(0, y_max, 5):
        cv.line(left, y(t), right, y(t), GRID)
        cv.text(left - 8, y(t) + 4, num(t, 0), "end", "s n")
    cv.text(left, top - 10, "basis points (1 = 0.01% of the swap)", "start", "s")
    cv.line(left, bottom, right, bottom, AXIS)
    month_ticks(cv, [w["week"] for w in weeks], x_of, bottom)
    index = {w["week"]: i for i, w in enumerate(weeks)}
    marks = []
    for key in ("before", "after", "latest"):
        win = f["windows"][key]
        i0 = index.get(win["start"])
        if i0 is None:
            continue
        i1 = i0 + win["weeks"]
        cv.line(x_of(i0) + 2, y(win["fee_rate_bps"]), x_of(i1) - 2, y(win["fee_rate_bps"]), BURGUNDY, 3)
        marks.append(((x_of(i0) + x_of(i1)) / 2, bottom - 12, f"{key}: {num(win['fee_rate_bps'], 1)}"))
    cv.polyline([(xm(i), y(w["fee_rate_bps"])) for i, w in enumerate(weeks)], CRIMSON)
    for mx, my, text in marks:
        cv.text(mx, my, text, "middle", "b n")
    rows = []
    for i, w in enumerate(weeks):
        cv.hit(x_of(i), top, step, bottom - top, f"Week of {day_label(w['week'])}: {num(w['fee_rate_bps'], 1)} basis points")
        rows.append([w["week"], num(w["fee_rate_bps"], 2)])
    ev = index.get(f["meta"]["event_date"])
    if ev is not None:
        event_marker(cv, x_of(ev), top - 2, bottom, "fee switch")
    return {"id": "fee", "svg": cv.svg(), "alt": "Weekly fee rate in basis points with window averages.",
            "columns": ["Week starting", "Fee rate (basis points)"], "rows": rows}


# --------------------------------------------------------------------------- 4

def basket(f: dict) -> dict:
    """NEAR Intents weekly volume against its fitted peer basket, and the gap between them."""
    sc = f["event_test"]["estimators"]["sc"]
    weeks = sc["weeks"]
    n = len(weeks)
    left, right, top, mid, top2, bottom = 56, W - 96, 30, 250, 292, 420
    cv = Canvas(462, "chart-basket", "NEAR Intents weekly volume against its peer basket",
                "Two lines of weekly volume per day and, below, the percent gap between them for each week.")
    values = [w["near_usd_per_day"] / 1e6 for w in weeks] + [w["basket_usd_per_day"] / 1e6 for w in weeks]
    y_max = 20 * math.ceil((max(values) + 5) / 20)
    y = linear(0, y_max, mid, top)
    step = (right - left) / n
    x_of = lambda i: left + i * step
    xm = lambda i: x_of(i) + step / 2
    for t in ticks(0, y_max, 20):
        cv.line(left, y(t), right, y(t), GRID)
        cv.text(left - 8, y(t) + 4, "$" + num(t, 0) + "M", "end", "s n")
    cv.line(left, mid, right, mid, AXIS)
    n_pre = sum(1 for w in weeks if w["period"] == "before")
    cv.polyline([(xm(i), y(w["basket_usd_per_day"] / 1e6)) for i, w in enumerate(weeks)], BLUE)
    cv.polyline([(xm(i), y(w["near_usd_per_day"] / 1e6)) for i, w in enumerate(weeks)], CRIMSON)
    for i, w in enumerate(weeks):
        cv.dot(xm(i), y(w["basket_usd_per_day"] / 1e6), 4, BLUE)
        cv.dot(xm(i), y(w["near_usd_per_day"] / 1e6), 4, CRIMSON)
    last = weeks[-1]
    y_near, y_bask = y(last["near_usd_per_day"] / 1e6), y(last["basket_usd_per_day"] / 1e6)
    if abs(y_near - y_bask) < 16:
        y_near, y_bask = (y_near - 8, y_bask + 8) if y_near <= y_bask else (y_near + 8, y_bask - 8)
    cv.text(right + 8, y_near + 4, "NEAR Intents", "start", "b")
    cv.text(right + 8, y_bask + 4, "peer basket", "start", "b")
    event_marker(cv, x_of(n_pre), top - 8, bottom, "fee switch")
    cv.text(x_of(n_pre) - 8, top + 4, "weights fitted on these weeks", "end", "s")
    gaps = [w["gap_pct"] for w in weeks]
    g_lo = 10 * math.floor((min(gaps) - 2) / 10)
    g_hi = 10 * math.ceil((max(gaps) + 2) / 10)
    yg = linear(g_lo, g_hi, bottom, top2)
    for t in ticks(g_lo, g_hi, 10):
        cv.line(left, yg(t), right, yg(t), GRID if t else AXIS)
        if t % 20 == 0:
            cv.text(left - 8, yg(t) + 4, pct(t, 0, True), "end", "s n")
    cv.text(left, top2 - 10, "NEAR Intents above (+) or below (−) the basket", "start", "s")
    bar = min(22.0, step - 4)
    rows = []
    for i, w in enumerate(weeks):
        cv.bar_signed(x_of(i) + (step - bar) / 2, yg(0), bar, yg(w["gap_pct"]), TAUPE if w["period"] == "before" else CRIMSON)
        tip = (f"Week of {day_label(w['week'])}: NEAR Intents {usd_m(w['near_usd_per_day'])} a day, "
               f"basket {usd_m(w['basket_usd_per_day'])}, gap {pct(w['gap_pct'], 1, True)}")
        cv.hit(x_of(i), top, step, bottom - top, tip)
        rows.append([w["week"], w["period"], usd_m(w["near_usd_per_day"]), usd_m(w["basket_usd_per_day"]), pct(w["gap_pct"], 1, True)])
    month_ticks(cv, [w["week"] for w in weeks], x_of, bottom)
    return {"id": "basket", "svg": cv.svg(), "alt": "NEAR Intents and peer-basket weekly volume with the weekly percent gap.",
            "columns": ["Week starting", "Period", "NEAR Intents per day", "Peer basket per day", "Gap"], "rows": rows}


# --------------------------------------------------------------------------- 5

def placebo(f: dict) -> dict:
    """The same test run on each peer, none of which had the fee switch."""
    et = f["event_test"]
    sc = et["estimators"]["sc"]
    units = [{"name": "NEAR Intents", "estimate_pct": sc["estimate_pct"], "lo_pct": sc["interval"]["lo_pct"],
              "hi_pct": sc["interval"]["hi_pct"], "determined": sc["interval"]["determined"],
              "pre_rmse_log": sc["pre_rmse_log"], "near": True}]
    units += [dict(u, near=False) for u in et["placebo"]["units"]]
    lo_axis, hi_axis = -70.0, 110.0
    left, right, top = 250, W - 28, 36
    row_h = 38
    bottom = top + row_h * len(units) + 6
    cv = Canvas(bottom + 46, "chart-placebo", "The same test applied to each peer",
                "Estimate and 90 percent interval for NEAR Intents and for each peer treated as if it had the fee switch.")
    x = linear(lo_axis, hi_axis, left, right)
    for t in ticks(lo_axis, hi_axis, 10):
        if t % 20 == 0:
            cv.line(x(t), top, x(t), bottom, GRID)
            cv.text(x(t), bottom + 18, pct(t, 0, True), "middle", "s n")
    cv.line(x(0), top - 6, x(0), bottom, INK2, 1.2)
    rows = []
    for i, u in enumerate(units):
        y = top + row_h * i + row_h / 2
        colour = CRIMSON if u["near"] else TAUPE
        cv.text(24, y - 2, u["name"], "start", "b")
        label = f"{pct(u['estimate_pct'], 1, True)}  ({pct(u['lo_pct'], 0, True)} to {pct(u['hi_pct'], 0, True)})" if u["determined"] else f"{pct(u['estimate_pct'], 1, True)}  (not determined)"
        cv.text(24, y + 14, label, "start", "s n")
        if u["determined"]:
            a, b = clip(u["lo_pct"], lo_axis, hi_axis), clip(u["hi_pct"], lo_axis, hi_axis)
            cv.add(f'<line x1="{c(x(a))}" y1="{c(y)}" x2="{c(x(b))}" y2="{c(y)}" stroke="{colour}" stroke-width="{6 if u["near"] else 4.5}" stroke-linecap="round"/>')
            if u["hi_pct"] > hi_axis:
                cv.text(right - 4, y - 8, "continues to " + pct(u["hi_pct"], 0, True), "end", "s n")
        cv.dot(x(clip(u["estimate_pct"], lo_axis, hi_axis)), y, 6.5 if u["near"] else 5.5, colour)
        cv.hit(left, y - row_h / 2, right - left, row_h, f"{u['name']}: {label}; fit error before the switch {num(u['pre_rmse_log'], 2)} log points")
        rows.append([u["name"], pct(u["estimate_pct"], 1, True), pct(u["lo_pct"], 1, True) if u["determined"] else "n/a",
                     pct(u["hi_pct"], 1, True) if u["determined"] else "n/a", num(u["pre_rmse_log"], 3)])
    cv.text(left, bottom + 38, "Estimated change after 23 Feb 2026, with the other peers as the comparison", "start", "s")
    return {"id": "placebo", "svg": cv.svg(), "alt": "Estimates and intervals for NEAR Intents and for each peer treated as a placebo.",
            "columns": ["Unit", "Estimate", "Interval low", "Interval high", "Fit error before (log points)"], "rows": rows}


# --------------------------------------------------------------------------- 6

def spec_curve(f: dict) -> dict:
    """Every clean specification, sorted by its estimate."""
    curve = f["spec_curve"]
    rows_all = [r for r in curve["rows"] if r["clean"]]
    n = len(rows_all)
    be = f["event_test"]["break_even_pct"]
    band = f["verdict"]["strict_band_pct"]
    left, right, top, bottom = 56, W - 20, 30, 300
    cv = Canvas(346, "chart-curve", "The estimate under every clean combination of analysis choices",
                "Sorted estimates of the volume change, with the plus or minus 15 percent band and the break-even loss.")
    values = [r["estimate_pct"] for r in rows_all] + [be, -band, band]
    lo_axis = 10 * math.floor((min(values) - 3) / 10)
    hi_axis = 10 * math.ceil((max(values) + 3) / 10)
    y = linear(lo_axis, hi_axis, bottom, top)
    x = linear(0, max(n - 1, 1), left + 6, right - 6)
    cv.rect(left, y(band), right - left, y(-band) - y(band), BAND)
    for t in ticks(lo_axis, hi_axis, 10):
        cv.line(left, y(t), right, y(t), GRID)
        cv.text(left - 8, y(t) + 4, pct(t, 0, True), "end", "s n")
    cv.line(left, y(0), right, y(0), INK2, 1.2)
    cv.line(left, y(be), right, y(be), BURGUNDY, 2)
    cv.text(right - 4, y(be) - 7, f"break-even {pct(be)}", "end", "b n")
    cv.text(right - 4, y(band) + 15, "±15% band", "end", "s n")
    cv.polyline([(x(i), y(r["estimate_pct"])) for i, r in enumerate(rows_all)], CRIMSON)
    width = (right - left) / max(n, 1)
    table = []
    for i, r in enumerate(rows_all):
        tip = (f"{pct(r['estimate_pct'], 1, True)}: {r['estimator']}, event {r['event_date']}, {r['pre_weeks']} weeks before, "
               f"{r['post_weeks']} after, {r['donor_set']} ({r['donors']} donors)")
        cv.hit(x(i) - width / 2, top, width, bottom - top, tip)
        table.append([str(i + 1), pct(r["estimate_pct"], 2, True), r["estimator"], r["event_date"], str(r["pre_weeks"]),
                      str(r["post_weeks"]), r["donor_set"], str(r["donors"])])
        if r["primary"]:
            cv.dot(x(i), y(r["estimate_pct"]), 6.5, BURGUNDY)
            cv.text(x(i) + 10, y(r["estimate_pct"]) + 22, f"primary specification {pct(r['estimate_pct'], 1, True)}", "start", "b n")
    cv.line(left, bottom, right, bottom, AXIS)
    cv.text(left, bottom + 22, f"{n} specifications, sorted from the largest loss to the largest gain", "start", "s")
    return {"id": "curve", "svg": cv.svg(), "alt": "Sorted estimates across all clean specifications with the band and break-even lines.",
            "columns": ["Rank", "Estimate", "Estimator", "Event date", "Weeks before", "Weeks after", "Donor set", "Donors"], "rows": table}


# --------------------------------------------------------------------------- 7

def growth(f: dict) -> dict:
    """Where the growth in revenue came from, before the switch against the latest window."""
    ch = f["changes"]["latest_vs_before"]
    items = [
        ("Revenue per day", ch["revenue_ratio_earned"], BURGUNDY),
        ("Volume", ch["volume_ratio"], CRIMSON),
        ("Fee rate users pay", ch["fee_rate_ratio"], CRIMSON),
        ("Share of fees NEAR keeps", ch["capture_ratio_earned"], CRIMSON),
    ]
    left, right, top = 250, W - 60, 30
    row_h = 44
    bottom = top + row_h * len(items)
    cv = Canvas(bottom + 46, "chart-growth", "What multiplied NEAR's revenue from Intents",
                "Bars on a ratio scale: revenue per day and its three factors, latest 13 weeks against the 13 weeks before the switch.")
    hi = max(8.0, 2 ** math.ceil(math.log2(max(v for _, v, _ in items) * 1.05)))
    lo = min(0.5, 2 ** math.floor(math.log2(min(v for _, v, _ in items) * 0.95)))
    x = linear(math.log(lo), math.log(hi), left, right)
    t = lo
    while t <= hi * 1.0001:
        cv.line(x(math.log(t)), top, x(math.log(t)), bottom, GRID if abs(t - 1) > 1e-9 else INK2, 1 if abs(t - 1) > 1e-9 else 1.2)
        cv.text(x(math.log(t)), bottom + 18, "×" + (num(t, 0) if t >= 1 else num(t, 2).rstrip("0")), "middle", "s n")
        t *= 2
    rows = []
    for i, (label, value, colour) in enumerate(items):
        y = top + row_h * i + row_h / 2
        x0, x1 = x(0.0), x(math.log(value))
        a, b = min(x0, x1), max(x0, x1)
        fill = colour if value >= 1 else BLUE
        r = min(4.0, (b - a) / 2)
        if value >= 1:
            cv.add(f'<path d="M{c(a)},{c(y - 10)} H{c(b - r)} Q{c(b)},{c(y - 10)} {c(b)},{c(y - 10 + r)} V{c(y + 10 - r)} Q{c(b)},{c(y + 10)} {c(b - r)},{c(y + 10)} H{c(a)} Z" fill="{fill}"/>')
            cv.text(b + 8, y + 5, "×" + num(value, 2), "start", "b n")
        else:
            cv.add(f'<path d="M{c(b)},{c(y - 10)} H{c(a + r)} Q{c(a)},{c(y - 10)} {c(a)},{c(y - 10 + r)} V{c(y + 10 - r)} Q{c(a)},{c(y + 10)} {c(a + r)},{c(y + 10)} H{c(b)} Z" fill="{fill}"/>')
            cv.text(a - 8, y + 5, "×" + num(value, 2), "end", "b n")
        cv.text(24, y + 5, label, "start", "b")
        cv.hit(left, y - row_h / 2, right - left, row_h, f"{label}: ×{num(value, 2)}")
        rows.append([label, "×" + num(value, 2)])
    cv.text(left, bottom + 38, "Latest 13 weeks divided by the 13 weeks before the switch. Volume × fee rate × share kept = revenue.", "start", "s")
    return {"id": "growth", "svg": cv.svg(), "alt": "Revenue per day and its three factors as ratios between two windows.",
            "columns": ["Measure", "Latest window divided by the window before the switch"], "rows": rows}


# --------------------------------------------------------------------------- 8

def share(f: dict) -> dict:
    """NEAR Intents' share of the peer basket by week, with the three window averages."""
    weeks = f["series"]["weekly"]
    n = len(weeks)
    left, right, top, bottom = 56, W - 20, 30, 290
    cv = Canvas(336, "chart-share", "NEAR Intents' share of swap volume in the peer basket, by week",
                "Weekly share line with the average for the window before the switch, the window after it and the latest window.")
    y = linear(0, 80, bottom, top)
    step = (right - left) / n
    x_of = lambda i: left + i * step
    xm = lambda i: x_of(i) + step / 2
    index = {w["week"]: i for i, w in enumerate(weeks)}
    first = dt.date.fromisoformat(weeks[0]["week"])
    x_day = lambda iso: left + (dt.date.fromisoformat(iso) - first).days / 7.0 * step
    for run in f["peers"]["outages"]:
        a, b = max(x_day(run["start"]), left), min(x_day(run["end"]) + step / 7.0, right)
        if b > a:
            cv.rect(a, top, b - a, bottom - top, BAND)
    for t in ticks(0, 80, 20):
        cv.line(left, y(t), right, y(t), GRID)
        cv.text(left - 8, y(t) + 4, pct(t, 0), "end", "s n")
    cv.line(left, bottom, right, bottom, AXIS)
    month_ticks(cv, [w["week"] for w in weeks], x_of, bottom)
    for run in f["peers"]["outages"]:
        if run["days"] >= 14 and x_day(run["start"]) >= left:
            cv.text(x_day(run["start"]) + 5, top + 14, f"{run['name']}:", "start", "s")
            cv.text(x_day(run["start"]) + 5, top + 29, "no volume reported", "start", "s")
    cv.polyline([(xm(i), y(w["share"] * 100)) for i, w in enumerate(weeks)], CRIMSON)
    for key in ("before", "after", "latest"):
        win = f["windows"][key]
        i0 = index.get(win["start"])
        if i0 is None:
            continue
        i1 = i0 + win["weeks"]
        cv.line(x_of(i0) + 2, y(win["share"] * 100), x_of(i1) - 2, y(win["share"] * 100), BURGUNDY, 3)
        cv.label((x_of(i0) + x_of(i1)) / 2, y(win["share"] * 100) + 22, pct(win["share"] * 100))
    rows = []
    for i, w in enumerate(weeks):
        cv.hit(x_of(i), top, step, bottom - top,
               f"Week of {day_label(w['week'])}: {pct(w['share'] * 100)} (NEAR Intents {usd_m(w['volume_per_day'])} a day, seven peers {usd_m(w['peers_volume_per_day'])})")
        rows.append([w["week"], pct(w["share"] * 100), usd_m(w["volume_per_day"]), usd_m(w["peers_volume_per_day"])])
    ev = index.get(f["meta"]["event_date"])
    if ev is not None:
        event_marker(cv, x_of(ev), top - 8, bottom, "fee switch")
    cv.text(left, bottom + 38, "Thick lines: share over each whole window. Shaded: days on which a peer reported no volume.", "start", "s")
    return {"id": "share", "svg": cv.svg(), "alt": "Weekly share of the peer basket with window averages.",
            "columns": ["Week starting", "Share", "NEAR Intents per day", "Seven peers per day"], "rows": rows}


def all_charts(f: dict) -> list:
    return [ruler(f), capture(f), fee_rate(f), basket(f), placebo(f), spec_curve(f), growth(f), share(f)]

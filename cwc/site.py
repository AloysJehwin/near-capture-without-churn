"""The dashboard: one static page, no external files, built from the findings.

The page works without JavaScript. A short inline script adds a hover read-out
for chart marks; every chart also has its data as a table underneath.
"""
from __future__ import annotations

import html
import re

from . import charts, report

REPO = "https://github.com/AloysJehwin/near-capture-without-churn"

CSS = """
:root{color-scheme:light;--ivory:#FBF6EA;--cream:#F4ECDA;--burgundy:#4A0E1C;--deep:#3A0A15;--crimson:#A8142D;--blue:#1D6996;
--ink:#2E0B13;--ink2:#5E4A44;--muted:#7A695D;--rule:#DCCFB6;
--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
--serif:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--cream);color:var(--ink);font:16px/1.55 var(--sans)}
a{color:var(--crimson);text-underline-offset:2px}
a:focus-visible,summary:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.wrap{max-width:1020px;margin:0 auto;padding:0 28px}
.mast{background:var(--burgundy);color:var(--ivory);padding:26px 0 150px}
.mast a{color:var(--ivory)}
.name{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;font-size:14px;color:#E4CFC6;margin-bottom:44px}
.name strong{color:var(--ivory);font-weight:600;letter-spacing:.01em}
h1{font:400 clamp(30px,4.6vw,50px)/1.12 var(--serif);margin:0 0 26px;max-width:21ch;letter-spacing:-.005em}
.answer{font:400 clamp(18px,2.1vw,22px)/1.45 var(--serif);max-width:60ch;margin:0 0 34px;color:#F3E6DC}
.answer b{font-family:var(--sans);font-size:.74em;font-weight:700;letter-spacing:.04em;background:var(--ivory);color:var(--burgundy);
padding:3px 9px 2px;border-radius:3px;margin-right:10px;white-space:nowrap;vertical-align:.12em}
.three{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0;margin:0;border-top:1px solid #7C3A47}
.three div{padding:16px 22px 0 0}
.three div+div{padding-left:22px;border-left:1px solid #7C3A47}
.three dt{font:600 30px/1.1 var(--sans);font-variant-numeric:tabular-nums;margin-bottom:6px}
.three dd{margin:0;font-size:14px;line-height:1.4;color:#E4CFC6;max-width:30ch}
.hero{margin-top:-118px}
.panel{background:var(--ivory);border:1px solid var(--rule);border-radius:6px;padding:20px 22px 12px}
.panel h2{margin-top:0}
main section{margin:54px 0 0}
h2{font:400 clamp(22px,2.6vw,29px)/1.2 var(--serif);margin:0 0 10px;max-width:34ch;color:var(--deep)}
h3{font:600 16px/1.3 var(--sans);margin:26px 0 8px}
p{margin:0 0 14px;max-width:70ch}
.lede{color:var(--ink2)}
.fig{margin:18px 0 0;overflow-x:auto}
svg.chart{display:block;width:100%;height:auto;min-width:640px;border-radius:6px}
.how{font-size:14px;color:var(--muted);margin:10px 0 0;max-width:86ch}
.how a{color:var(--ink2)}
details{margin:8px 0 0;font-size:14px}
summary{cursor:pointer;color:var(--ink2);padding:4px 0;width:max-content}
.scroll{overflow-x:auto;max-height:340px;overflow-y:auto;border:1px solid var(--rule);border-radius:6px;background:var(--ivory);margin-top:6px}
table{border-collapse:collapse;width:100%;font-size:14px;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:6px 12px;border-bottom:1px solid var(--rule);vertical-align:top}
th{position:sticky;top:0;background:var(--ivory);font-weight:600;color:var(--ink2)}
tr:last-child td{border-bottom:0}
.plain table{background:var(--ivory);border:1px solid var(--rule);border-radius:6px}
ol.against{padding-left:22px;max-width:74ch}
ol.against li{margin:0 0 12px}
ol.against b{font-weight:600}
ul.notes{padding-left:20px;max-width:78ch;margin:18px 0 0}
ul.notes li{margin:0 0 10px}
ul.notes b{font-weight:600}
footer{margin:64px 0 0;padding:26px 0 44px;border-top:1px solid var(--rule);font-size:14px;color:var(--ink2)}
#tip{position:fixed;z-index:9;max-width:340px;background:var(--deep);color:var(--ivory);font-size:13px;line-height:1.4;padding:7px 10px;border-radius:4px;pointer-events:none}
.note{background:var(--ivory);border-left:4px solid var(--crimson);padding:12px 16px;margin:0 0 18px;max-width:74ch}
@media (max-width:720px){.wrap{padding:0 18px}.three{grid-template-columns:1fr}.three div+div{padding-left:0;border-left:0;border-top:1px solid #7C3A47;margin-top:14px}
.mast{padding-bottom:120px}.hero{margin-top:-96px}.panel{padding:14px 12px 8px}}
"""

JS = """
(function(){var tip=document.getElementById('tip');if(!tip)return;
function place(x,y){var w=tip.offsetWidth,h=tip.offsetHeight,l=x+14,t=y+16;
if(l+w>window.innerWidth-8)l=x-w-14;if(l<8)l=8;if(t+h>window.innerHeight-8)t=y-h-12;
tip.style.left=l+'px';tip.style.top=t+'px';}
function show(e){var el=e.target.closest?e.target.closest('[data-tip]'):null;
if(!el){tip.hidden=true;return;}tip.textContent=el.getAttribute('data-tip');tip.hidden=false;place(e.clientX,e.clientY);}
document.addEventListener('mousemove',show);document.addEventListener('click',show);
document.addEventListener('scroll',function(){tip.hidden=true;},true);
document.addEventListener('mouseleave',function(){tip.hidden=true;});})();
"""


def minus(text: str) -> str:
    """Show a real minus sign in front of numbers. Dates and hyphenated words are left alone."""
    return re.sub(r"(?<![\w-])-(?=\d)", "\u2212", text)


def e(value) -> str:
    return html.escape(minus(str(value)), quote=True)


def data_table(chart: dict) -> str:
    head = "".join(f'<th scope="col">{e(col)}</th>' for col in chart["columns"])
    body = "".join("<tr>" + "".join(f"<td>{e(cell)}</td>" for cell in row) + "</tr>" for row in chart["rows"])
    return (f'<details><summary>Show the data ({len(chart["rows"])} rows)</summary>'
            f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></details>')


def md_table_to_html(markdown: str) -> str:
    lines = [line for line in markdown.splitlines() if line.strip()]
    cells = lambda line: [c.strip() for c in line.strip().strip("|").split("|")]
    head = "".join(f'<th scope="col">{e(c)}</th>' for c in cells(lines[0]))
    body = "".join("<tr>" + "".join(f"<td>{e(c)}</td>" for c in cells(line)) + "</tr>" for line in lines[2:])
    return f'<div class="plain"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def sources(f: dict, keys: list) -> str:
    by_key = {s["key"]: s for s in f["snapshot"]}
    links = []
    for key in keys:
        s = by_key[key]
        label = s["name"] + " " + s["measure"].replace("_", " ")
        links.append(f'<a href="{html.escape(s["url"], quote=True)}">{e(label)}</a>')
    return "Source: DefiLlama, " + ", ".join(links) + "."


def figure(chart: dict, how: str, src: str) -> str:
    return (f'<div class="fig">{chart["svg"]}</div><p class="how">{how} {src}</p>{data_table(chart)}')


def render(f: dict) -> str:
    v = report.facts(f)
    ch = {c["id"]: c for c in charts.all_charts(f)}
    near_keys = ["near_intents_volume", "near_intents_fees", "near_intents_revenue", "near_intents_revenue_by_label"]
    peer_keys = [s["key"] for s in f["snapshot"] if s["role"] == "peer"]
    label = v["verdict_label"].capitalize()
    banner = ""
    if not f["verdict"]["prose_matches"]:
        banner = ('<p class="note"><strong>Read this first.</strong> These numbers were rebuilt and the outcome of the tests changed. '
                  'The verdict and every figure are current; some explanatory sentences were written for a different outcome.</p>')
    if not f["verdict"]["interval_determined"]:
        hero = "The test could not put a bound on the volume change"
    elif f["verdict"]["claims"]["paid_for_itself"]:
        hero = "The loss that would cancel the gain is outside the interval"
    else:
        hero = "The interval reaches the loss that would cancel the gain"
    cfg = f["config"]
    against = [
        f"<b>A real loss cannot be ruled out.</b> The interval reaches {v['interval_lo']}. A loss of up to {v['loss_bound']} is consistent with the data, so the strict form of the claim (no loss beyond {v['strict_band']}) fails.",
        f"<b>The gap was drifting down when the test had to stop.</b> NEAR Intents ran {v['gap_first']} against its basket in the first {v['gap_first_weeks']} weeks and {v['gap_second']} in the last {v['gap_second_weeks']}; {v['gap_last_three']} in the last three. Then {v['first_outage_phrase']}.",
        f"<b>The basket follows NEAR Intents only loosely.</b> Typical weekly gap before the switch: {v['fit_error']} log points. Pretending the switch happened on {v['backtest_date']}, the test reports {v['backtest']} where the truth is zero.",
        f"<b>One of three estimators cannot rule out break-even.</b> The pooled-volume estimator gives {v['estimate_pooled']} ({v['pooled_lo']} to {v['pooled_hi']}).",
        f"<b>Some window choices disagree.</b> Of {v['rob_count']} combinations of event date and window, the break-even loss is ruled out in {v['rob_holds']}, not determined in {v['rob_not_determined']} and not ruled out in {v['rob_fails']}. In {v['rob_loss_detected']} the whole interval is below zero.",
        f"<b>How much the cut rose depends on the window:</b> {v['take_ratio_min']}x to {v['take_ratio_max']}x, which puts the break-even loss between {v['break_even_smallest']} and {v['break_even_largest']}. As DefiLlama books the transfers, the capture ratio reads {v['capture_ratio_booked']}x; spread over the days the money was earned it is {v['capture_ratio']}x.",
        f"<b>Volume did fall in dollars.</b> NEAR Intents volume {v['volume_moved_after']} after the switch. The peers together {v['peers_moved_after']}.",
        f"<b>The later rise has no test of its own.</b> The share of fees NEAR keeps went from {v['capture_after']} to {v['capture_latest']} after the test window, with no dated change to test.",
        "<b>The rules were written after a first look at the data.</b> No out-of-sample test exists yet; the dated check below is the only one.",
    ]
    pf = report.partner_facts(f)
    bold = lambda text: re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(text, quote=False))
    if pf["partners_available"]:
        against += [bold(item) for item in pf["partner_against_items"][:2]]
    else:
        against.append("<b>Total volume cannot show which partners stayed.</b> That needs swap-level data from NEAR's Explorer API.")
    partner_block = []
    if pf["partners_available"]:
        pv = f["partners"]
        partner_block = [
            f'<section><h2>The {e(pf["partner_top_count"])} largest partner apps sent {e(pf["partner_top_after"])} their earlier volume after the switch, and {e(pf["partner_top_latest"])} now</h2>',
            f'<p class="lede">Totals can hold while single partners leave. NEAR\'s own swap records name the partner app behind each swap. This is a sample of {e(pf["partner_swaps"])} of them, taken at fixed hours on every day, '
            f'covering the part of NEAR Intents that runs through its 1Click service (about {e(pf["partner_coverage_before"])} of volume before the switch). '
            f'{e(pf["partner_gone_count"])} of the {e(pf["partner_top_count"])} fell below a tenth of their earlier volume: {e(pf["partner_gone_names"])}.</p>',
            figure(ch["partners"], "Dollars in each window's sampled blocks divided by the time those blocks span. Taken with a partner key; stored as totals per partner app.",
                   f'Source: <a href="https://explorer.near-intents.org/api/v0/transactions">NEAR Intents Explorer API</a>, sample fingerprint {html.escape(pv["files"][0]["sha256"][:12])}.'),
            '<ul class="notes">' + "".join(f"<li>{minus(bold(item))}</li>" for item in pf["partner_for_items"] + pf["partner_against_items"][2:]) + "</ul>",
            "</section>",
        ]
    snapshot_rows = "".join(
        f"<tr><td>{e(s['name'])}</td><td>{e(s['measure'].replace('_', ' '))}</td><td>{e(s['role'])}</td>"
        f"<td>{e(s['first_day'] or '')} to {e(s['last_day'] or '')}</td><td>{e(s['fetched_at_utc'])}</td>"
        f"<td><a href=\"{html.escape(s['url'], quote=True)}\">{html.escape(s['sha256'][:12])}</a></td></tr>" for s in f["snapshot"])
    parts = [
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Capture without churn: NEAR Intents after the fee switch</title>",
        '<meta name="description" content="Did NEAR Intents lose swap volume when NEAR started taking a share of partner fees? An evidence dashboard rebuilt offline from a hashed DefiLlama snapshot.">',
        f"<style>{CSS}</style></head><body>",
        '<header class="mast"><div class="wrap">',
        f'<div class="name"><strong>Capture without churn</strong><span>NEAR Hackathon, Investment Thesis track. Data through {e(report.long_date(v["data_through"]))}.</span></div>',
        "<h1>When NEAR started taking a share of partner fees, did the swaps leave?</h1>",
        f'<p class="answer"><b>{e(label.upper())}</b>{e(v["verdict_sentence"])}</p>',
        '<dl class="three">',
        f'<div><dt>{e(v["take_ratio"])}x</dt><dd>NEAR\'s take per dollar swapped, {e(v["after_weeks"])} weeks after the switch against {e(v["before_weeks"])} weeks before</dd></div>',
        f'<div><dt>{e(v["break_even"])}</dt><dd>the fall in volume that would have cancelled the gain</dd></div>',
        f'<div><dt>{e(v["estimate"])}</dt><dd>what volume did against {e(v["peer_count"])} peers; {e(v["interval_level"])} interval {e(v["interval_lo"])} to {e(v["interval_hi"])}</dd></div>',
        "</dl></div></header>",
        '<main class="wrap">',
        f'<section class="hero"><div class="panel">{banner}<h2>{hero}</h2>',
        f'<p class="lede">Each bar is the range the volume change can be in, at the {e(v["interval_level"])} level, under one way of comparing NEAR Intents with its peers. '
        f'Left of the dark line, lost volume would have cost more than the higher cut brought in. The main estimate rules out a fall of more than {e(v["loss_bound"])}; it does not rule out a fall of {e(v["strict_band"])}.</p>',
        figure(ch["ruler"], "Log weekly volume of NEAR Intents against its peers; permutation interval after Chernozhukov, Wüthrich and Zhu.",
               sources(f, ["near_intents_volume"] + peer_keys)),
        "</div></section>",

        f'<section><h2>NEAR\'s take per $100 swapped went from {e(v["take_before"])} to {e(v["take_after"])} cents</h2>',
        f'<p class="lede">Before the switch NEAR earned little from swaps that partner apps sent: its share of partner fees, with smaller items, was {e(v["other_before"])} of all fees (red). '
        f'In the {e(v["after_weeks"])} weeks after it was {e(v["other_after"])}, and in the latest {e(v["latest_weeks"])} weeks {e(v["other_latest"])}. The blue part is NEAR\'s own app.</p>',
        figure(ch["capture"], "Revenue by DefiLlama label divided by gross fees, week by week. Front-end transfers are spread back over the days they were earned.",
               sources(f, ["near_intents_revenue_by_label", "near_intents_fees"])),
        "</section>",

        f'<section><h2>Users paid {e(v["fee_before"])} cents per $100 before and {e(v["fee_after"])} after</h2>',
        f'<p class="lede">If partners had passed the cost on, this line would step up at the switch. {e(v["pass_through_sentence"])} In the latest {e(v["latest_weeks"])} weeks it is {e(v["fee_latest"])} cents.</p>',
        figure(ch["fee"], "Gross fees divided by swap volume, by week. The thick lines are the same ratio over each whole window.",
               sources(f, ["near_intents_fees", "near_intents_volume"])),
        "</section>",

        f'<section><h2>NEAR Intents volume {e(v["volume_moved_after"])}; its peers {e(v["peers_moved_after"])}</h2>',
        f'<p class="lede">The blue line is a weighted mix of peers ({e(v["weights"])}) chosen to follow NEAR Intents before the switch. '
        f'After the switch NEAR Intents ran {e(v["estimate"])} against it on average: {e(v["gap_first"])} in the first {e(v["gap_first_weeks"])} weeks and {e(v["gap_second"])} in the last {e(v["gap_second_weeks"])}. '
        f'The window ends where it does because {e(v["first_outage_phrase"])}.</p>',
        figure(ch["basket"], "Synthetic control with an intercept on log weekly volume; weights are not negative and sum to one.",
               sources(f, ["near_intents_volume"] + peer_keys)),
        "</section>",

        f'<section><h2>Run on each peer, the same test finds an effect in {e(v["placebo_excluding_zero"])} of {e(v["placebo_units"])}</h2>',
        f'<p class="lede">None of the peers had a fee switch on that date, so a sound test should find nothing. NEAR Intents\' fit before the switch {e(v["fit_rank_phrase"])}.</p>',
        figure(ch["placebo"], "Each peer in turn is treated as if it had the switch, with the remaining peers as its comparison.",
               sources(f, peer_keys)),
        "</section>",

        f'<section><h2>{e(v["curve_clean"])} ways of running the test: median {e(v["curve_median"])}, lowest {e(v["curve_min"])}</h2>',
        f'<p class="lede">Every combination of {1 + len(cfg["alt_event_dates"])} event dates, {len(cfg["spec_curve"]["pre_weeks"])} lengths of the period before, {len(cfg["spec_curve"]["post_weeks"])} after, the peer sets and 3 estimators. '
        f'{e(v["curve_within"])} of the results are inside the band and {e(v["curve_below"])} show a loss of more than {e(v["strict_band"])}. '
        f'A further {e(v["curve_not_clean"])} runs overlap a peer outage; they are left out of this chart and of the rules.</p>',
        figure(ch["curve"], f'{e(v["curve_planned"])} combinations planned, {e(v["curve_duplicates"])} dropped as duplicates and {e(v["curve_too_few"])} for too few valid peers.',
               sources(f, ["near_intents_volume"] + peer_keys)),
        "</section>",

        f'<section><h2>Since then revenue is {e(v["revenue_ratio_latest"])}x, and {e(v["growth_from_capture"])} of that growth is the higher cut</h2>',
        f'<p class="lede">Revenue is volume times the fee rate times the share NEAR keeps, so its growth splits exactly into those three. Latest {e(v["latest_weeks"])} weeks against the {e(v["before_weeks"])} before the switch.</p>',
        figure(ch["growth"], "Ratios of window totals. Shares of growth are shares of the log change.",
               sources(f, near_keys)),
        "</section>",

        f'<section><h2>Share of the peer basket: {e(v["share_before"])} before, {e(v["share_after"])} after, {e(v["share_latest"])} now</h2>',
        f'<p class="lede">NEAR Intents volume divided by its own plus the {e(v["basket_count"])} peers\'. Week to week it swings with the largest peer; over whole windows it has barely moved. '
        f'Leaving any one peer out, the change to the latest window is between {e(v["share_change_latest_min"])} and {e(v["share_change_latest_max"])} points.</p>',
        figure(ch["share"], "Plain sums of daily volume. A day on which a peer reports nothing counts as zero for that peer.",
               sources(f, ["near_intents_volume"] + peer_keys)),
        "</section>",

        *partner_block,

        '<section><h2>What counts against the thesis</h2><ol class="against">' + "".join(f"<li>{minus(item)}</li>" for item in against) + "</ol></section>",

        "<section><h2>What would change the verdict</h2>",
        f'<p>The verdict is computed by fixed rules. It turns to "not supported" if the take fails to rise under any window choice, if the interval reaches the break-even loss, '
        f'if the estimate is below −{e(v["strict_band"])} and more than {e(v["kill_share"])} of the clean runs are too, or if, in the latest {e(v["latest_weeks"])} weeks, NEAR keeps less than {e(v["share_floor"])} of fees '
        f'or its share of the basket is more than {e(v["share_drop_limit"])} points below the level before the switch.</p>',
        f'<p>The last rule will be read again on the first snapshot with data through the day before {e(report.long_date(v["forward_date"]))}. Status today: {e(v["forward_status"])}.</p>',
        "</section>",

        "<section><h2>Who the peers are, and who was left out</h2>",
        f'<p class="lede">Bridge aggregators are taken from DefiLlama\'s list of {e(v["universe_entries"])} by rule: at least {e(v["size_rule"])} of volume in the past year, not flagged as double-counted, '
        f'and weekly volume in each of the {e(v["history_rule_weeks"])} weeks before the switch. Adding the excluded ones back moves the main estimate to {e(v["with_candidates"])}.</p>',
        md_table_to_html(v["table_peers"]),
        "</section>",

        "<section><h2>The data</h2>",
        f'<p class="lede">Every file is DefiLlama\'s response stored unchanged. The rebuild stops if a file does not match its hash. Snapshot fingerprint {e(v["manifest_sha"])}.</p>',
        f'<div class="scroll"><table><thead><tr><th scope="col">Service</th><th scope="col">Measure</th><th scope="col">Role</th><th scope="col">Days covered</th><th scope="col">Fetched (UTC)</th><th scope="col">SHA-256</th></tr></thead><tbody>{snapshot_rows}</tbody></table></div>',
        "</section>",
        "</main>",
        f'<footer><div class="wrap"><p>Rebuild every number on this page: <code>python3 -m cwc rebuild</code>. No packages, no network, no key. '
        f'<a href="{REPO}">Repository</a>, <a href="{REPO}/blob/main/THESIS.md">thesis</a>, <a href="{REPO}/blob/main/out/findings.json">findings.json</a>.</p>'
        "<p>Data: DefiLlama. This page is research, not investment advice.</p></div></footer>",
        '<div id="tip" role="status" hidden></div>',
        f"<script>{JS}</script></body></html>",
    ]
    return "\n".join(parts) + "\n"

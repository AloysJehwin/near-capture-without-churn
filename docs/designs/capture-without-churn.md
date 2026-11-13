# Capture without churn

*   **Author:** Aloys Jehwin (GitHub: AloysJehwin)
*   **Status:** Built. This revision describes the system as implemented.
*   **Date:** 2026-11-14
*   **History:** The first draft (2026-11-13) was reviewed by three independent
    reviewers before any code existed. Their findings and what was done about
    each are in `docs/designs/reviews/2026-11-13-first-review.md`. This revision
    replaces that draft.

--------------------------------------------------------------------------------

## Overview

This project is an entry for the NEAR Hackathon, Investment Thesis track. The
track asks for a long-term investment thesis on NEAR backed by evidence another
person can reproduce. Entries are first screened by AI coding agents that run
the repository and check that it does what its README says. Human judges then
decide.

Background a reader needs:

*   **NEAR** is a blockchain. Its token is also called NEAR. In this document
    "NEAR" as an actor means the organisations that run NEAR Intents and
    receive its revenue.
*   **NEAR Intents** is a service that swaps one crypto asset for another
    across blockchains.
*   A **partner** is a wallet or app that sends its users' swaps to NEAR
    Intents and adds a fee. The user pays that fee.
*   **Fees** are all fees users pay on NEAR Intents swaps. **Revenue** is the
    part of fees that reaches NEAR. **Capture** is revenue divided by fees.
    **Take** is revenue divided by swap volume.
*   The **fee switch** is what NEAR calls the automatic split of partner fees
    between the partner and NEAR, switched on in late February 2026. NEAR's
    documentation gives a default split of 50/50 with other terms by
    agreement. NEAR uses its part to buy NEAR tokens.
*   **DefiLlama** is a public data site that publishes daily volume, fees and
    revenue for crypto protocols through a free web API.

The thesis tested: NEAR can take a larger share of fees without losing the
swaps. A partner that loses part of its fee can leave (volume falls against
rivals), charge users more (the fee rate rises) or accept it. The project
measures all three.

The project is a Python program with no third-party packages. It reads a
committed snapshot of data, computes every number once, applies fixed decision
rules, and writes a results file, a thesis document, a README block, a
dashboard and its charts. One command rebuilds everything offline.

## The Problem

Other entries in this track report that NEAR Intents earns fees and that
buybacks offset part of token issuance. One entry
([bomanaps/-near-intents-thesis](https://github.com/bomanaps/-near-intents-thesis))
compares NEAR Intents volume with three same-chain swap aggregators around the
same date. That comparison has three gaps: the comparison group does not sell
the same product; "no significant change" is not evidence of "no loss", since a
noisy test also fails to detect large losses; and it does not say what size of
loss would matter.

This project asks a sharper question. If NEAR's take per dollar swapped goes
from `t0` to `t1`, NEAR's revenue goes up unless volume falls by more than
`1 - t0/t1`. That figure is the **break-even loss**. The project estimates how
NEAR Intents volume moved against cross-chain peers after the fee switch and
reports the largest loss the data cannot rule out. If that is smaller than the
break-even loss, the higher cut paid for itself.

## Goals

*   One claim, decided by fixed rules that are written in code and applied in a
    fixed order, with every threshold in one configuration file.
*   Measure the change in NEAR's take, with revenue moved onto the days it was
    earned.
*   Estimate the change in NEAR Intents volume against a basket of peers after
    the fee switch, with a 90 percent interval, and compare its lower end with
    the break-even loss.
*   Check the method on units that had no fee switch, on a backdated event and
    with two simpler estimators.
*   Show how the answer depends on analysis choices (a specification curve).
*   Select bridge-aggregator peers by a stated rule that the code enforces.
*   Report evidence against the claim with numbers.
*   Rebuild every number, chart and sentence that quotes a number with one
    offline command, using only the Python standard library (3.10 or later),
    and prove that the committed outputs equal a fresh rebuild byte for byte.

## Non-Goals

*   Predicting the price of the NEAR token.
*   Proving that the fee switch caused any change in volume. The design
    measures what happened and states what else happened at the same time.
*   On-chain data from NEAR's public BigQuery tables.
*   Live or scheduled refresh. The snapshot is refreshed by hand.
*   A blind test. The rules were written after an exploratory look at the same
    data. This is disclosed in THESIS.md, and one dated check on future data is
    defined.

## Open Questions

*   **Second hackathon entry.** The hackathon reportedly requires that a
    person with two entries names each in the other's README. The author has
    to say whether there is a second entry.
*   **Public dashboard link.** GitHub Pages can serve `docs/index.html`. The
    repository setting has to be changed by the author.

## Critical User Journeys (CUJs)

### CUJ 1: An AI screener checks the repository

*   **Given**: A fresh clone, Python 3.10 or later, no network, no API keys.
*   **When**: The screener runs `python3 -m cwc verify`, then
    `python3 -m unittest discover -s tests`, then `python3 -m cwc rebuild`.
*   **Then**: `verify` lists every output file as `identical` and exits 0,
    which shows the committed files are what the code produces from the
    committed data. The tests pass. `rebuild` lists every file as `unchanged`
    and prints the verdict and headline numbers. Changing one byte of a raw
    data file makes both commands stop with a hash mismatch.

### CUJ 2: A judge reads the result

*   **Given**: A browser, or GitHub's file view.
*   **When**: The judge opens `docs/index.html`, or reads `README.md` and
    `THESIS.md` on GitHub.
*   **Then**: The page shows the question, the verdict, three headline
    numbers and the charts, each with its sources, one line on how it is
    computed and its data as a table. On GitHub the charts appear as images in
    README.md and THESIS.md, because each chart is also a separate SVG file.

### CUJ 3: A sceptic changes an assumption

*   **Given**: The repository and a text editor.
*   **When**: The sceptic edits `config/analysis.json` (for example the number
    of weeks before the event) and runs `python3 -m cwc rebuild`.
*   **Then**: Every number, the verdict line and every chart change together.
    If the outcome of the rules now differs from the one the thesis prose was
    written for (`written_for` in the configuration), THESIS.md, the README
    block and the dashboard carry a warning that says so.

### CUJ 4: The author refreshes the data

*   **Given**: Network access.
*   **When**: The author runs `python3 scripts/refresh.py`, then
    `python3 -m cwc rebuild`.
*   **Then**: Every response is downloaded and checked before anything on disk
    changes. `data/raw/` then holds the new files and a new manifest. The
    verdict can change. `git diff` shows which numbers moved.

## Technical Plan (Architecture)

### Data

All public data comes from DefiLlama's free API. No key is needed. Each
response is stored unchanged in `data/raw/`, and `MANIFEST.json` records its
address, fetch time, size and SHA-256. `config/series.json` is the single
registry of series and their roles.

| Role | Series |
| --- | --- |
| treated | NEAR Intents daily volume, fees, revenue, holders revenue, and revenue by label |
| peer | daily volume of THORChain, Chainflip, Maya Protocol (swap protocols) and LI.FI, SOCKET, Rango, Bungee (bridge aggregators) |
| candidate | daily volume of bridge aggregators that pass the size rule but fail another rule: Jumper, OpenSea, Silentswap, Bitget Wallet X, 0x |
| universe | DefiLlama's list of bridge aggregators with trailing-year volume |

DefiLlama splits NEAR's revenue into two labels: revenue from NEAR's own front
end, and other revenue (its share of partner fees, and smaller items). Before
late April 2026 the front-end revenue reaches NEAR's wallet in transfers up to
46 days apart, and DefiLlama books each transfer on the day it is made. The
loader moves each transfer back onto the days since the previous one, in
proportion to the fees charged on each day. Revenue measured this way is
called **earned**; DefiLlama's own figure is called **booked**. The tests use
earned revenue and report both.

An optional second source is a sample of NEAR's own swap records (see
"Partner view").

### Peers

The three swap protocols are the ones a large integrator's documentation lists
beside NEAR Intents. The bridge aggregators are selected by rule from the
universe file: trailing-year volume of at least one billion dollars, not
flagged `doublecounted` by DefiLlama, and weekly volume defined in each of the
26 weeks before the event. The rebuild stops if the rule and the registry
disagree. Candidates that fail a rule stay in the snapshot so the exclusion
can be checked and reversed: one donor set in the specification curve adds
them back.

DefiLlama's bridge-volume data (Relay, Across, deBridge) required payment when
the snapshot was taken, so those services are not peers.

### Time

*   A week runs Monday to Sunday, UTC.
*   Weekly volume of a unit is defined only if at least five of its seven days
    have a value above zero; it is the sum of those days scaled to seven.
*   An **outage** is a run of at least three days on which a peer reports zero
    or nothing.
*   The **event** is 2026-02-23: DefiLlama dates NEAR's buyback programme from
    that day and its holders-revenue series starts that day; NEAR's post of
    the next day says the fee switch is live. Revenue from partner fees first
    appears on 2026-01-31, so 2026-02-02 is a second event date in the
    robustness runs.
*   **Before** is the 13 weeks before the event. **After** is the weeks from
    the event up to the first peer outage, which is 11 weeks; the code checks
    that 11 is the longest outage-free run. **Latest** is the last 13 complete
    weeks in the snapshot.

### Measures

Over a window, from plain sums of daily values: capture (booked and earned,
and by label), fee rate in basis points, take in basis points, NEAR Intents'
share of the volume of itself plus the peers, and that share with each peer
left out. Between two windows: ratios, the break-even change
`take(before) / take(after) - 1`, and the exact split
`ln(revenue ratio) = ln(volume ratio) + ln(fee-rate ratio) + ln(capture ratio)`.

### Event test

Outcome: natural log of weekly volume. Three estimators share one interface.
Each builds a comparison series from the valid peers, removes the average gap
over the weeks before the event, and reports the average gap after it.

*   **Synthetic control** (main): peer weights that are not negative and sum
    to one, chosen to track NEAR Intents before the event, plus an intercept.
    The weights are found exactly: for every subset of peers the problem with
    weights only forced to sum to one is a linear system; subsets with a
    negative weight are dropped; the feasible subset with the smallest squared
    error wins. The systems are inverted once and reused.
*   **Equal-weight difference**: the mean of the peers' logs.
*   **Pooled-volume difference**: the log of the peers' summed volume.

A peer is a **valid donor** in a window if its weekly volume is defined in
every week of the window and no declared change of definition falls inside it
(SOCKET's series changes definition on 2026-06-11; the code checks that date
against the text in the raw file).

**Interval.** For a candidate shift, remove it from the weeks after the event,
refit on all weeks, and compare the absolute mean of the last residuals with
the same statistic under every cyclic shift of the residuals (Chernozhukov,
Wüthrich and Zhu). The 90 percent interval is the set of candidates on a grid
that are not rejected, widened by one grid step at each end. If the accepted
set touches an end of the grid the interval is "not determined", and the rules
treat that as a failure.

**Checks on the method.** The same test is run on each peer as if it had the
fee switch, with the other peers as donors; the number of intervals that
exclude zero is reported. The event is backdated inside the weeks before it
(fit on the first 8, pretend effect over the last 5); the result should be
zero. The gap is reported for the first and second part of the weeks after,
and for the last three.

### Specification curve

Every combination of event date (2), weeks before (9, 13, 17), weeks after (7,
9, 11, 13, 26), donor set (all peers; protocols only; aggregators only; each
peer left out; peers plus candidates) and estimator (3). A combination is
**clean** if no peer outage falls inside its window; only clean ones count in
the rules. Two donor sets that resolve to the same valid donors in the same
window are one specification. Combinations with fewer than two valid donors
are skipped. All counts are reported.

The same event test with its own break-even is also run for every clean
combination of event date and window, to show in how many the break-even loss
is ruled out.

### Decision rules

Applied in this order; the first that fails decides.

1.  The cut rose: the earned take ratio is above 1 in every clean window
    choice.
2.  The interval is determined.
3.  It paid for itself: the lower end of the interval is above the break-even
    change.
4.  Not (the estimate is below -15 percent and more than half of the clean
    specifications are too).
5.  Share held since: in the latest window capture is at least 20 percent and
    NEAR Intents' share of the basket is not more than 10 points below its
    level before the event, with any one peer left out.

If any fails: NOT SUPPORTED. Otherwise, if the whole interval is below zero:
SUPPORTED IN PART (a loss was detected, smaller than break-even). Otherwise,
if the lower end is at or above -15 percent: SUPPORTED. Otherwise: SUPPORTED
IN PART (a smaller loss cannot be ruled out).

Rule 5 is read again on the first snapshot whose last complete week ends on or
after 2027-02-14. Until then the forward check reads "not yet due". No clock
is used: "due" depends only on the snapshot.

### Partner view

The NEAR Intents Explorer API lists single swaps made through NEAR's 1Click
service with the partner that sent each one and the accounts its app fees are
paid to. It needs a partner key. `scripts/explorer_sample.py` takes a fixed
sample: for each UTC day and each of a few fixed hours, up to 1,000 successful
swaps that end at that time. It stores only totals per partner and per fee
account for each block, with the seconds the block spans. It stores no sender,
recipient, deposit address or transaction hash, and never stores or prints the
key.

`cwc/partners.py` reads the stored sample (with its own hash check) and
computes, for the three windows: dollars per day (sum of dollars over sum of
seconds), the split of volume between partners, NEAR's own apps and swaps with
no referral, the app fee charged, the share of app fees paid to NEAR's
wallets, and a table of the ten largest partners before the event with their
volume before, after and latest. NEAR's own apps are identified from the data:
referrals whose app fees go mostly to NEAR's front-end wallet. The partner
view is evidence beside the rules; it does not enter the verdict. If the
sample file is absent the project builds without this section.

### Outputs

One function builds all outputs in memory and returns them as bytes:

*   `out/findings.json`: every number, the verdict, data and configuration
    hashes. Floats are rounded to 6 decimals and keys sorted.
*   `THESIS.md`: `thesis/THESIS.template.md` with `{{name}}` placeholders
    filled by `cwc/report.py`. An undefined placeholder stops the build. The
    template contains no typed results; a test enforces that.
*   `README.md`: the block between two markers is rewritten.
*   `docs/index.html`: one page, no external files. It works without
    JavaScript; a short inline script adds a hover read-out.
*   `docs/charts/*.svg`: each chart as a self-contained file.

`verify` compares these bytes with the files on disk and changes nothing.
`rebuild` writes them and reports which changed.

### Data flow

```text
config/series.json --> scripts/refresh.py --> data/raw/*.json + MANIFEST.json      (network, by hand)
partner key ---------> scripts/explorer_sample.py --> data/explorer/*.json         (network, by hand, optional)
                                   |
config/analysis.json --------------+
                                   v
                 python3 -m cwc rebuild | verify     (offline)
   hash checks -> peer rule -> windows and measures -> event test and checks
   -> window grid -> specification curve -> share rule -> verdict -> partner view
                                   |
        +-----------------+--------+---------+----------------------+
        v                 v                  v                      v
 out/findings.json   THESIS.md, README   docs/index.html      docs/charts/*.svg
```

## Alternatives Considered

### Alternative A: Difference-in-differences against same-chain aggregators

*   **Pros**: Simple, and already used by another entry.
*   **Cons**: Same-chain aggregators do not move assets across chains, so
    their volume answers to different demand.
*   **Decision**: Not used. The comparison group is the weak point of the
    existing result. The equal-weight estimator here is the same idea applied
    to cross-chain peers.

### Alternative B: A simple difference as the main estimator

*   **Pros**: Nothing is fitted but an intercept, so it cannot overfit 13
    weekly points.
*   **Cons**: Its gap before the event is larger (0.22 and 0.30 log points
    against 0.14 for synthetic control), which widens the interval.
*   **Decision**: Synthetic control is the main estimator; both differences
    are reported beside it with their own intervals and backtests. In the
    backtest synthetic control is not better than the equal-weight difference,
    and THESIS.md says so.

### Alternative C: Third-party packages (numpy, scipy, a causal-inference library)

*   **Pros**: Less code to write and review.
*   **Cons**: The screener would have to install packages, possibly without a
    network, and results could differ across versions.
*   **Decision**: Standard library only. The cost is about 200 lines for the
    exact solver and 400 for the SVG charts. Outputs are byte-identical on
    Python 3.10 to 3.13.

### Alternative D: A plus or minus 15 percent band as the only test

*   **Pros**: One threshold.
*   **Cons**: The band is a judgment call and says nothing about revenue.
*   **Decision**: The break-even loss, which is derived from the data, decides
    whether the claim is supported at all. The band decides between
    "supported" and "supported in part".

### Alternative E: Daily data

*   **Pros**: More points, and a finer p-value (steps of one over the number
    of days, against one over the number of weeks).
*   **Cons**: A day-of-week pattern and single-day reporting gaps that differ
    across services would have to be modelled.
*   **Decision**: Weekly. With 24 weeks the p-value moves in steps of 1/24,
    which is fine enough for a 90 percent interval. A daily version is listed
    under Future Improvements.

### Alternative F: An estimator with a trend term

*   **Pros**: Would absorb a steady drift of NEAR Intents against its peers.
*   **Cons**: Two more parameters on 13 points.
*   **Decision**: Not used. The backtest and the first-part and second-part
    gaps are reported so a drift is visible.

### Alternative G: Share of the basket alone

*   **Pros**: No model. Anyone can recompute it.
*   **Cons**: Week to week it swings with the largest peer.
*   **Decision**: Reported for whole windows and used in rule 5, with each
    peer left out in turn.

--------------------------------------------------------------------------------

## Non-Functional Requirements

*   **No secrets**: The repository holds no key. `.gitignore` lists `.env`.
    Only `scripts/explorer_sample.py` reads a key, from the environment or a
    local `.env`, and never writes or prints it.
*   **Offline**: `rebuild` and `verify` open no network connection. A test
    replaces `socket.socket` and rebuilds.
*   **Determinism**: No clock, random number or iteration order reaches an
    output. Sums use `math.fsum`. Outputs are rounded at 6 decimals. Verified
    byte-identical on Python 3.10, 3.11, 3.12 and 3.13 on one machine; a
    difference in the platform's `exp` or `log` at the last bit could in
    principle move a rounded figure on another machine.
*   **Integrity**: The build stops if any data file differs from its recorded
    hash. `.gitattributes` turns off line-ending conversion.
*   **Runtime**: About 10 seconds.

## Risks and Limits

| Risk | Effect | What is done |
| --- | --- | --- |
| The basket follows NEAR Intents loosely | Wide interval; the method's error may be larger than the interval suggests | Fit error, backtest and peer placebo results are reported; the verdict cannot be "supported" unless a 15 percent loss is ruled out |
| Revenue is booked when moved, not when earned | Capture before the event depends on transfer dates | Front-end transfers are moved onto the days they were earned; booked and earned figures are both reported; the take ratio is reported over every window choice |
| The event is not a clean switch | Partner revenue appears three weeks earlier; products were announced the same week | A second event date in the robustness runs; stated under limits in THESIS.md |
| A peer outage sends its users elsewhere | Longer windows flatter NEAR Intents | The window after the event ends before the first outage; windows with an outage do not count in the rules |
| Few peers, with shocks of their own | One peer can move the estimate | Leave-one-out donor sets; the rule-based peer list |
| Bridge aggregators route through other services, including NEAR Intents | The basket is an index, not a market total | Stated; share is reported with each peer left out |
| A series changes definition | A break that is not real | Declared in the registry, checked against the raw file, and the series is not a donor in windows that contain the change |
| DefiLlama revises history | Numbers move between snapshots | The snapshot is committed with hashes and fetch times |
| Rules written after seeing the data | Not a blind test | Disclosed; configuration hash in the findings; one dated check on future data |
| The partner sample is a sample, taken at fixed hours | Shares and levels carry sampling error and a time-of-day pattern | Block counts and a jackknife error are reported; the partner view does not enter the verdict |
| Later rise in capture has no dated event | No test of its own | Covered only by rule 5 and by description |

--------------------------------------------------------------------------------

### Additional Resources

*   Track brief: <https://github.com/nearai/near-hackathon-prompt-examples/blob/main/tracks/02-thesis.md>
*   NEAR, "Evolving NEAR Tokenomics": <https://near.org/blog/evolving-near-tokenomics>
*   NEAR Intents documentation, fees: <https://docs.near-intents.org/resources/fees>
*   Abadie, Diamond, Hainmueller (2010), "Synthetic Control Methods for Comparative Case Studies".
*   Doudchenko, Imbens (2016), arXiv 1610.07748.
*   Chernozhukov, Wüthrich, Zhu (2021), arXiv 1712.09089.
*   Lakens (2017), "Equivalence Tests".
*   Simonsohn, Simmons, Nelson (2020), "Specification curve analysis".

### Future Improvements

*   A daily version of the event test.
*   A complete download of swap records for the weeks around the event, in
    place of a sample.
*   An on-chain cross-check of DefiLlama's volume.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

Python 3.10 or later, standard library only. Package `cwc`.

### Files

| File | Responsibility |
| --- | --- |
| `config/series.json` | Registry of data series: key, name, role, group, address, declared definition changes |
| `config/analysis.json` | Every analysis choice and threshold, and `written_for` (the outcome the thesis prose was written for) |
| `scripts/refresh.py` | Download the public snapshot; write nothing unless every response is sound |
| `scripts/explorer_sample.py` | Take the partner sample with a key; store totals only |
| `cwc/data.py` | Hash checks, loading, weekly rule, window sums, outages, moving transfers onto the days they were earned |
| `cwc/pool.py` | The peer rule and the check of declared definition changes |
| `cwc/metrics.py` | Window measures, break-even, comparison of two windows |
| `cwc/synth.py` | Exact simplex least squares, the three estimators, the permutation interval |
| `cwc/speccurve.py` | Donor sets, valid donors, clean windows, the specification curve |
| `cwc/verdict.py` | The decision rules, the share rule, the forward check |
| `cwc/partners.py` | The partner view from the stored sample |
| `cwc/pipeline.py` | Runs everything in order and returns the findings dictionary |
| `cwc/charts.py` | The charts as self-contained SVG strings with data tables |
| `cwc/report.py` | Every formatted figure and generated sentence; fills the thesis template and the README block |
| `cwc/site.py` | The dashboard page |
| `cwc/__main__.py` | `verify` and `rebuild` |
| `thesis/THESIS.template.md` | Thesis text with placeholders and no typed results |
| `tests/` | Unit tests for each module, a tamper test, an offline rebuild, and a comparison of committed outputs with a fresh build |

### Verification Plan

*   **Build**: `python3 -m cwc verify` exits 0 on a fresh clone.
*   **Unit tests**: `python3 -m unittest discover -s tests`, all passing.
*   **Compile check**: `python3 -m compileall -q cwc scripts tests`.
*   **Other Python versions**: verify and tests on 3.10, 3.11, 3.12, 3.13.
*   **Fresh clone**: clone from GitHub into an empty directory and run the
    three commands of CUJ 1.
*   **Blind review**: a reviewer with no context follows the README and checks
    quoted numbers against `out/findings.json`.

--------------------------------------------------------------------------------

*Drafted and reviewed with the Elephant-Goldfish Model (EGM) process: a
document is written with full context, then read by reviewers who see only the
document.*

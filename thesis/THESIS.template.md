# Capture without churn

**Thesis.** NEAR can take a larger share of the fees on NEAR Intents swaps without losing the swaps. If that is true, NEAR has pricing power over cross-chain swap flow, and the revenue that pays for NEAR buybacks can grow faster than volume.

**Verdict: {{verdict_label}}.** {{verdict_sentence}}

{{banner}}Every figure in this file is written by `python3 -m cwc rebuild` from a committed data snapshot. Data run through {{data_through}}. The snapshot was fetched {{snapshot_fetched}}. Nothing here is typed by hand, and nothing is estimated from memory.

## 1. The question in plain words

NEAR Intents swaps one crypto asset for another across blockchains. Wallets and apps (called partners here) send their users' swaps to it and add a fee on top. The user pays that fee. Until early 2026 NEAR earned little from partners' swaps: in the {{before_weeks}} weeks before the change, its share of partner fees, together with smaller items, came to {{other_before}} of all fees paid, and {{front_share_of_revenue_before}} of NEAR's revenue from Intents came from its own app.

In late February 2026 NEAR turned on what it calls the fee switch: an automatic split of partner fees between the partner and NEAR. NEAR's documentation gives the default split as 50/50, with other terms possible by agreement. NEAR uses its part to buy NEAR tokens on the open market. This file dates the switch to {{event_date_long}}; section 8 says why.

A partner that has to hand over half of its fee has three choices:

1. Send its swaps somewhere else. Then NEAR Intents volume falls against its rivals.
2. Charge users more to make up the difference. Then the fee users pay per dollar swapped goes up.
3. Accept it. Then neither of those moves.

This file tests the first two with public data. In one sentence: {{one_line}}

## 2. The numbers

{{table_windows}}

How to read it:

* "Share of fees NEAR kept" is NEAR's revenue divided by all fees users paid. DefiLlama splits that revenue into two labelled parts, and both are shown.
* "Take per $100 swapped" is revenue divided by volume. It equals the fee rate times the share NEAR kept. It is the number that matters for NEAR's revenue: revenue = volume x take.
* NEAR's own app sends its revenue to NEAR's wallet in transfers that were up to {{front_longest_gap}} days apart, and DefiLlama counts each transfer on the day it was made. This file moves each transfer back onto the days it was earned. Without that step the share NEAR kept reads {{capture_booked_before}} before and {{capture_booked_after}} after ({{capture_ratio_booked}}x). With it, {{capture_before}} and {{capture_after}} ({{capture_ratio}}x). The smaller, corrected figures are used everywhere.

## 3. Evidence for the thesis

**3.1 The cut rose.** NEAR's take per $100 swapped went from {{take_before}} cents to {{take_after}} cents, {{take_ratio}}x. The rise is in the part the fee switch created: NEAR's share of partner fees, together with smaller items, was {{other_before}} of all fees before and {{other_after}} after. That part is paid every day from {{other_daily_from}}, so its timing is not in doubt. Across {{grid_count}} choices of event date and window length, the main one included, the take after the switch was between {{take_ratio_min}}x and {{take_ratio_max}}x its level before.

![Share of fees that reached NEAR, by week and source](docs/charts/capture.svg)

**3.2 Did users pay more?** The fee users paid per $100 swapped was {{fee_before}} cents before and {{fee_after}} cents after. {{pass_through_sentence}}

![Fees users pay per dollar swapped, by week](docs/charts/fee.svg)

**3.3 Volume against rivals.** NEAR Intents volume {{volume_moved_after}} after the switch. The {{basket_count}} comparison services together {{peers_moved_after}} over the same weeks. NEAR Intents' share of the combined volume was {{share_before}} before and {{share_after}} after.

The formal test builds a weighted basket of the {{peer_count}} peers that tracked NEAR Intents before the switch ({{weights}}) and asks how far NEAR Intents moved away from it afterwards. The answer is {{estimate}}, with a {{interval_level}} interval of {{interval_lo}} to {{interval_hi}}.

**3.4 The gain against the break-even loss.** With the take at {{take_ratio}}x, revenue only falls if volume drops by more than {{break_even}}. That is the break-even loss. The interval ends at {{interval_lo}}, which is {{interval_margin}} points away from it. NEAR's revenue per day was {{revenue_ratio_after}} times its level before.

![Volume change against peers with the break-even loss](docs/charts/ruler.svg)

**3.5 The answer does not hang on one choice.** The same test was run for {{rob_count}} combinations of event date and window length. The break-even loss was ruled out in {{rob_holds}} of them. Across {{curve_clean}} specifications that also vary the peer set and the estimator, the estimate has a median of {{curve_median}} and runs from {{curve_min}} to {{curve_max}}. {{curve_below}} of them show a loss of more than {{strict_band}}. The lowest is {{curve_margin}} points above the break-even loss.

![The estimate under every clean combination of analysis choices](docs/charts/curve.svg)

**3.6 The test does not find effects that are not there.** Each of the {{placebo_units}} peers was put through the same test as if it had had the fee switch. The interval excluded zero for {{placebo_excluding_zero}} of them. NEAR Intents' fit before the switch {{fit_rank_phrase}}.

{{table_placebo}}

**3.7 Since then.** In the latest {{latest_weeks}} weeks NEAR kept {{capture_latest}} of fees, {{capture_ratio_latest}}x the level before the switch. Volume is {{volume_ratio_latest}}x and the peers' volume {{peers_ratio_latest}}x. NEAR Intents' share of the basket is {{share_latest}}, against {{share_before}} before. Revenue per day is {{revenue_ratio_latest}}x. Splitting that growth exactly into its three factors, {{growth_from_capture}} came from the higher cut, {{growth_from_volume}} from volume and {{growth_from_fee_rate}} from the fee rate.

![What multiplied NEAR's revenue from Intents](docs/charts/growth.svg)

![NEAR Intents' share of the peer basket by week](docs/charts/share.svg)

## 4. Evidence against the thesis

**4.1 A real loss cannot be ruled out.** The interval reaches {{interval_lo}}. The strict form of the claim, that a loss of more than {{strict_band}} is ruled out, fails. The largest loss the data cannot rule out is {{loss_bound}}.

**4.2 The gap was drifting down when the test had to stop.** NEAR Intents ran {{gap_first}} against its basket in the first {{gap_first_weeks}} weeks after the switch and {{gap_second}} in the last {{gap_second_weeks}}. In the last three weeks it was {{gap_last_three}}. The test cannot be extended: {{first_outage_phrase}}, and their users had to go somewhere. THORChain's own report dates an exploit and a trading halt to 15 May 2026.

**4.3 The basket follows NEAR Intents only loosely.** Before the switch the weekly gap between the two had a typical size of {{fit_error}} log points, about the same as the {{strict_band}} line. When the weights are fitted on the first {{backtest_fit_weeks}} weeks only and the "switch" is pretended to happen on {{backtest_date}}, the test reports {{backtest}} where the true answer is zero.

**4.4 The result depends on the estimator at the margin.** The two simpler estimators give {{estimate_equal}} ({{equal_lo}} to {{equal_hi}}) and {{estimate_pooled}} ({{pooled_lo}} to {{pooled_hi}}). The second one sums the peers' volume, so the largest peer drives it. {{pooled_break_even_phrase}}, and its backtest error is {{backtest_pooled}}.

{{table_estimators}}

**4.5 Some window choices disagree.** Of the {{rob_count}} combinations, the interval could not be determined in {{rob_not_determined}} and the break-even loss was not ruled out in {{rob_fails}} ({{rob_failed_case}}). In {{rob_loss_detected}} the whole interval is below zero, which is a detected loss ({{rob_detected_case}}).

**4.6 How much the cut rose depends on the window.** The take ratio is {{take_ratio}}x for the main windows and as low as {{take_ratio_min}}x for others, which puts the break-even loss anywhere from {{break_even_smallest}} to {{break_even_largest}}.

**4.7 Volume did fall.** In dollars, NEAR Intents volume {{volume_moved_after}} after the switch. The claim is only that rivals fell about as much.

**4.8 The later rise has no test of its own.** NEAR's share of fees went from {{capture_after}} in the test window to {{capture_latest}} in the latest one. No dated change is documented for that, so there is no before and after to compare. Longer windows are not a substitute. A peer's outage sends its users elsewhere, so a window that includes one is biased. The {{curve_not_clean}} specifications of that kind have a median of {{curve_not_clean_median}}. They are shown but do not count.

**4.9 The rules were written after a first look at the data.** The thresholds are in `config/analysis.json`, and its hash is in `out/findings.json`, but they were chosen after an exploratory run on the same data. No out-of-sample test exists yet. The only one is the dated check in section 7.

## 5. Partner by partner, from NEAR's own swap records

{{partner_section}}

## 6. What these data cannot show

* {{partner_gap_bullet}}
* **Cause.** Other things happened in the same week: NEAR announced new products together with the fee switch (press release of 25 February 2026). The test measures what happened to volume, not why.
* **Whether the money was new.** Before {{other_daily_from}} DefiLlama records almost no revenue from partner fees. If NEAR was owed such revenue earlier and only started moving it then, the rise in the cut is overstated.
* **One short stretch of front-end revenue.** Front-end transfers are recorded daily only from {{front_daily_from}}. Before that there were {{front_transfers_lumpy}} transfers, and the correction in section 2 assumes each one was earned evenly, in proportion to fees, since the one before.
* **A true market share.** The basket is {{basket_count}} services with a free daily volume series. Bridge aggregators route through other services, possibly including NEAR Intents, so the basket is an index, not a market total.

## 7. What would change the verdict

The verdict is computed by fixed rules in `cwc/verdict.py`. It becomes NOT SUPPORTED if any of these happens on a rebuild:

1. NEAR's take fails to rise under any one of the window choices.
2. The interval for the volume change reaches the break-even loss.
3. The estimate is below -{{strict_band}} and more than {{kill_share}} of the clean specifications are too.
4. In the latest {{latest_weeks}} weeks NEAR keeps less than {{share_floor}} of fees (it gave the cut back), or NEAR Intents' share of the basket is more than {{share_drop_limit}} points below its level before the switch, whichever peer is left out. Today this rule {{share_check_result}}: the share moved by {{share_change_latest}} points ({{share_change_latest_min}} to {{share_change_latest_max}} leaving one peer out).

**Dated check.** Rule 4 will be read again on the first snapshot whose data run through the day before {{forward_date}}. Status today: {{forward_status}}.

{{partner_verdict_note}}

## 8. Method

* **Data.** DefiLlama's free API, no key. Daily volume, fees and revenue for NEAR Intents, revenue by label, and daily volume for the peers. Every response is stored unchanged in `data/raw/` with its address, fetch time and SHA-256 in `data/raw/MANIFEST.json`. The rebuild stops if a file does not match.
* **Event.** {{event_date}}. NEAR's post of 24 February 2026 says the fee switch is live. DefiLlama dates NEAR's buyback programme from {{event_date}}, and its buyback series is first above zero on {{holders_first_day}}. Revenue from partner fees first appears earlier, on {{other_daily_from}}, so {{alt_event_date}} is used as a second event date in the robustness runs.
* **Windows.** Weeks run Monday to Sunday, UTC. {{before_weeks}} weeks before the event and {{after_weeks}} weeks after. {{after_weeks}} is not a choice: it is every whole week before the first peer outage ({{longest_clean_post}} weeks are available).
* **Weekly volume.** A week counts only if at least five of its seven days have a value above zero. Its volume is the sum of those days scaled to seven.
* **Main estimator.** Synthetic control with an intercept on log weekly volume: weights on the peers that are not negative and sum to one, chosen to track NEAR Intents over the weeks before the event. The weights are found exactly by solving every subset of peers, not by an iterative search.
* **Interval.** The permutation method of Chernozhukov, Wuthrich and Zhu. For each candidate effect, take it out of the weeks after the event, refit on all weeks, and compare the mean of the last {{after_weeks}} residuals with the same mean under every cyclic shift. The interval is the set of candidates not rejected at the {{interval_level}} level, widened by one grid step at each end.
* **Break-even.** Revenue is volume times take. If take goes from t0 to t1, revenue is unchanged when volume changes by t0 / t1 - 1.
* {{partner_method_bullet}}
* **Peers.** The three native cross-chain swap protocols that SwapKit lists beside NEAR Intents, and every bridge aggregator in DefiLlama's list of {{universe_entries}} that has at least {{size_rule}} of volume in the past year, is not flagged as double-counted, and has weekly volume in each of the {{history_rule_weeks}} weeks before the event. The rebuild stops if the peers in the configuration differ from what these rules select. Adding the excluded candidates back changes the main estimate to {{with_candidates}}.

{{table_peers}}

## 9. Reproduce

```
python3 -m cwc verify      # rebuilds in memory and compares with the committed files
python3 -m cwc rebuild     # rewrites out/findings.json, THESIS.md, the README block and docs/
python3 -m unittest discover -s tests
```

Python 3.10 or later. No packages to install, no network, no key. Snapshot fingerprint {{manifest_sha}}, configuration fingerprint {{config_sha}}.

## 10. Not computed

* On-chain volume from NEAR's public BigQuery tables. The question is about volume, fees and revenue, which DefiLlama already publishes.
* Volume for Relay, Across and deBridge. DefiLlama's bridge-volume data answered "payment required" when this snapshot was taken, so they are not peers.
* A test on daily data. Weekly sums remove the day-of-week pattern and single-day reporting gaps. The cost is a coarser test: the p-value moves in steps of one over the number of weeks.
* Any price forecast for the NEAR token.

## 11. Disclosures

* The code and text in this repository were written with Claude (Anthropic) under the author's direction. The design was reviewed by separate AI reviewers and revised; the design and the review notes are in `docs/designs/`.
* No third-party code. Python standard library only.
* Data: DefiLlama, and for section 5 a sample from NEAR's Explorer API taken with the author's partner key. External facts: the sources below.

## 12. Sources

* NEAR, "Evolving NEAR Tokenomics", 24 February 2026: <https://near.org/blog/evolving-near-tokenomics>
* NEAR Intents documentation, fees: <https://docs.near-intents.org/resources/fees>
* NEAR Intents Explorer API (partner key required): <https://explorer.near-intents.org/api/v0/transactions>
* DefiLlama, NEAR Intents (methodology notes are stored in the raw files): <https://defillama.com/protocol/near-intents>
* NEAR, press release "NEAR Unveils Confidential Cross-Chain Infrastructure for the Agentic Economy", 25 February 2026: <https://tools.prnewswire.com/en-us/live/20813/release/20260225EN95768>
* THORChain, exploit report for 15 May 2026: <https://blog.thorchain.org/thorchain-exploit-report-1>
* SwapKit, NEAR Intents compared with THORChain, Maya Protocol and Chainflip: <https://swapkit.dev/?p=2374>
* Abadie, Diamond, Hainmueller (2010), "Synthetic Control Methods for Comparative Case Studies", Journal of the American Statistical Association.
* Doudchenko, Imbens (2016), "Balancing, Regression, Difference-in-Differences and Synthetic Control Methods": <https://arxiv.org/abs/1610.07748>
* Chernozhukov, Wuthrich, Zhu (2021), "An Exact and Robust Conformal Inference Method for Counterfactual and Synthetic Controls": <https://arxiv.org/abs/1712.09089>
* Lakens (2017), "Equivalence Tests: A Practical Primer", Social Psychological and Personality Science.
* Simonsohn, Simmons, Nelson (2020), "Specification curve analysis", Nature Human Behaviour.

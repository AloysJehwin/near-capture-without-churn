# First review of the design, 2026-11-13

The first draft of `docs/designs/capture-without-churn.md` was read by
independent AI reviewers who saw only the document (the "Goldfish" step of the
Elephant-Goldfish Model process). Each looked at one thing: scope, whether a
new reader can follow it, the design itself, whether it can be built as
written, and technical accuracy. This log lists what changed between the first draft and the design as built.
Items 1 to 3 came from the reviewers. The others came from the review or from
problems met while building; the notes do not always say which. The current
design document already includes all of them.

| # | Finding | Severity | What was done |
| --- | --- | --- | --- |
| 1 | The headline measure (revenue divided by fees) jumps on the days NEAR's own app moves its revenue to NEAR's wallet. Those transfers were up to 46 days apart, so the ratio before the event depends on where the window edges fall. | Blocker | Checked against the data and confirmed. Each transfer is now moved back onto the days it was earned, in proportion to fees. The tests use this "earned" basis and report DefiLlama's "booked" figures beside it. The first rule became "the take rose under every clean window choice", not "under the main window". |
| 2 | The break-even loss was defined on capture, but revenue also depends on the fee rate. | Major | Break-even is now defined on take (revenue divided by volume), which is the fee rate times capture. |
| 3 | The peer list was chosen by hand. A reader cannot tell whether peers were picked to get a result. One candidate (Jumper) is flagged by DefiLlama as double-counted. | Major | Bridge aggregators are now selected by a written rule from DefiLlama's own list, and the rebuild stops if the rule and the list in the configuration disagree. Candidates that fail a rule stay in the snapshot, and one run adds them back. |
| 4 | With few weeks on each side the permutation test cannot reject anything, and the interval silently becomes the whole search grid. | Major | The interval now carries a "determined" flag. An interval that touches an end of the grid counts as a failure in the rules. The grid was widened. |
| 5 | The verdict rules were described in prose in two places that could drift apart. | Major | One ordered procedure in `cwc/verdict.py`, every threshold in `config/analysis.json`, and the outcome the thesis text was written for is recorded so a changed outcome raises a visible warning. |
| 6 | Windows that include a peer's outage flatter NEAR Intents, because the peer's users go elsewhere. | Major | Outages are found from the data. The window after the event ends before the first one, and runs whose window contains one do not count in the rules. |
| 7 | Sentences in the thesis stated results that could change on a rebuild. | Minor | The thesis is a template with placeholders. Sentences that depend on the data are generated. A test fails if a result is typed into the template. |
| 8 | A disclosure sentence about the author's holdings had no source. | Minor | Removed. |

Two later checks are recorded here as well:

* Two independent "blind judge" runs on the pushed repository, one acting as
  the AI screener and one as a sceptical panel.
* A second review of this revision of the design document.

Their findings are added to this folder when the runs are complete.

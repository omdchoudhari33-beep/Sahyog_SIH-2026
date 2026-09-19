# Priority scoring and transparency

## How priority is decided

Every active ticket in the Triage and Route queue gets a priority score
based on a combination of factors:

- **Severity** — how serious the reported issue is.
- **Cluster size** — how many separate reports have been merged into this
  one ticket (more reports of the same issue means more people affected,
  so it counts toward higher priority).
- **Age** — how long the ticket has been sitting active; older tickets
  gain a small priority boost so nothing sits forgotten indefinitely.
- **Population impact** — an estimate of how many people the issue
  affects.

The human operator reviewing the queue sees this score alongside every
ticket, sorted with the highest-priority tickets first, so the most urgent
or widely-affecting issues are looked at sooner.

## The transparency layer

A separate public transparency stage publishes the current status of every
ticket that has moved out of the initial triage queue, so anyone — not just
the citizen who filed it — can see what's been reported, how it was routed,
and where it currently stands. This is the same status data the tracking
page reads from when you look up a ticket by its ID.

# Duplicate handling

When several citizens report the same underlying problem (say, the same
pothole, or the same water outage in a neighbourhood), the system tries to
recognise that they're describing one issue rather than opening a separate
ticket for each report.

## How a duplicate is detected

1. **Location check**: when a new report comes in, the system first looks
   for other still-active tickets reported near the same location.
2. **Meaning check**: among those nearby tickets, it compares what the new
   report is actually describing against what each nearby ticket already
   says, using a semantic similarity comparison rather than just matching
   exact words.
3. **Merge decision**: if a nearby ticket describes a similar-enough
   problem, the new report is folded into it instead of creating a new
   ticket — the existing ticket's "cluster count" (how many reports have
   been folded into it) goes up by one, and its severity/population-impact
   estimates are raised to the highest value reported so far.
4. If no nearby ticket is a close enough match, the new report becomes its
   own, brand-new active ticket.

## Why this matters to you

- If your report gets merged into an existing ticket, that's expected
  behaviour, not an error — it means someone already reported the same
  issue, and your report has strengthened its priority rather than been
  lost.
- A ticket with a higher cluster count (more people reporting the same
  thing) is treated as higher priority, since it likely affects more
  people.

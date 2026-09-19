# Track A vs. Track B

Once a ticket has been triaged, deduplicated, and prioritised, a human
operator decides how it should be handled: Track A, Track B, or reject/merge
if it turns out not to be a real, actionable, distinct issue.

## Track A — routine municipal repair

Track A is for issues that are a normal municipal fix: a pothole, a broken
streetlight, an overflowing drain, and similar routine repairs. These
tickets are routed to the correct Urban Local Body (ULB) department, which
is contacted (via API or email), given a service-level window to respond,
and asked for closure proof once the work is done.

## Track B — research or innovation needed

Track B is for issues that a routine repair crew can't really solve on its
own: a recurring public-health pattern, a pollution source that needs
identifying, a livelihood or irrigation problem that needs redesigning, or
illegal construction/encroachment that needs investigation. These tickets
are matched to a higher-education institution (HEI) with relevant research
capability, which forms a team and submits a project proposal. Once a
nodal officer approves that proposal, the project is tracked through
milestones and a pilot validation before it's handed back to a ULB or, in
some cases, spun out as a startup.

## Who decides

The Evidence Extractor stage already offers an AI-suggested track based on
the report's content and complexity, and the Triage and Route stage
surfaces that suggestion — but a human operator always makes the final
Track A / Track B call before anything is dispatched. The AI's suggestion
is a starting point for the operator, never an automatic decision.

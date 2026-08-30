# Decision Log

## Project

Skylark Drones Monday.com Business Intelligence Agent

## Goal

Build a conversational BI agent that answers founder-level questions using live monday.com data from deal and work-order boards while handling messy real-world data gracefully.

## Key Assumptions

1. The monday.com boards are the source of truth, not local CSV files.
2. The integration is read-only, as required by the assignment.
3. Board column names may vary slightly after import, so the code should tolerate a small set of aliases.
4. Historical analysis should be based on the most relevant available date fields for each metric, even when the underlying data is incomplete.
5. Founder-level questions should default to concise, decision-oriented answers with caveats rather than raw table dumps.

## Major Decisions

### 1. Streamlit for the prototype UI

I used Streamlit to deliver a fast hosted-prototype-friendly interface within the assignment time limit. It allowed me to build a conversational front end, a KPI snapshot, and a leadership-summary view quickly without spending most of the time on frontend infrastructure.

Trade-off:

- Faster product delivery
- Less control than a custom frontend stack

### 2. monday.com GraphQL API instead of MCP

I used the monday.com API directly through a lightweight client. This gave explicit control over authentication, pagination, request retries, and DataFrame construction.

Trade-off:

- More implementation effort than using a higher-level connector
- Better transparency and portability for the submission

### 3. Deterministic BI tools for calculations

I kept the business calculations in Python rather than relying on the model to derive metrics from raw records. This reduces hallucination risk and makes results testable.

Trade-off:

- Safer and more auditable outputs
- Narrower out-of-the-box coverage than a fully free-form agent

### 4. Hybrid conversational architecture

The agent first tries deterministic routing for known BI patterns such as pipeline, collections, cross-board comparison, sector comparisons, and overview questions. It only falls back to the LLM when the question does not match those structured patterns.

Trade-off:

- More reliable for important assignment-style questions
- Still not a fully general BI copilot for every possible business query

### 5. Explicit data-quality caveats

I chose to surface missing fields, incomplete records, and historical-filter exclusions directly in the final answer. For BI use cases, silent failure or silent imputation would be more dangerous than a slightly more verbose response.

Trade-off:

- Better analytical honesty
- Slightly less polished-looking answers than overly simplified summaries

### 6. Best-effort historical time filtering

The assignment expects questions like `last month` and `this quarter`. I implemented real time-window filtering using the best available date fields rather than ignoring the user’s requested period.

Interpretation:

- Deals use close-date style fields first, then fallback fields
- Work-order metrics use different date bases depending on the metric
- If no usable date is available, the system reports that limitation

Trade-off:

- Better alignment with the assignment
- Historical answers still depend on the quality of the source board dates

## How I Interpreted "Leadership Updates"

I interpreted this as helping a founder or leadership team quickly prepare a compact operating summary from live business data.

That resulted in:

- a one-click leadership summary view
- concise headline metrics across pipeline and execution
- explicit data-quality caveats
- founder-friendly wording instead of analyst-heavy output

I did not interpret it as generating a full slide deck, email draft, or scheduled report workflow because that would likely be beyond the intended time box.

## What I Would Do With More Time

1. Add hosted deployment and production config
2. Expand conversational coverage using a richer semantic intent layer
3. Add more robust operational metrics such as execution throughput, aging receivables, and billing velocity
4. Improve historical modeling for monthly and quarterly snapshots
5. Add end-to-end tests with fixture datasets that mirror the actual monday.com boards
6. Add observability for query tracing, tool selection, and data-quality diagnostics
7. Add export options for leadership updates such as markdown, PDF, or email-ready briefs

## Main Trade-Off Summary

I optimized for correctness, transparency, and assignment-fit over breadth. The result is a stronger prototype for structured founder BI workflows, even though it is not yet a fully general business copilot.

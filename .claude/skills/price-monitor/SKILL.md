---
name: price-monitor
description: >
  Maintain this price-comparison project, investigate its scrapers, data pipeline,
  public site or scheduled refresh, and add another retailer alongside Zococity.
  Use when changing store integrations or diagnosing stale or incorrect prices.
---

# Price monitor for Zococity and other retailers

Use this skill for changes to product matching, retailer data collection, the
comparison UI, publication, or scheduled refreshes in this repository.

## Workflow

1. Read the root `CLAUDE.md`, `README.md`, and the relevant current code. For the
   original Zococity/PCComponentes behavior, consult
   `download/zoco-pcc-monitor/SKILL.md` as historical implementation detail; verify
   it against the code before relying on it.
2. Keep Zococity's `handle` as the canonical catalog identity unless the user asks
   to change the catalog model. Treat every retailer as a separate offer source.
3. Before changing the public JSON schema, find every producer and consumer:
   `pipeline.py`, `scripts/build_public.py`, the generated static page, local UI,
   exports, and any API route. Update them together and preserve old snapshots or
   provide a compatible migration.
4. For a new retailer, use the matching and data rules in
   `references/adding-a-retailer.md`. Keep its network/parsing logic in a focused
   adapter rather than adding retailer-specific branches throughout the pipeline.
5. Make the smallest change that preserves the current two-store behavior. Verify
   extraction with saved fixtures or a small bounded sample before running a full
   live scrape. Ask before production runs, deployment, scheduling, or account and
   credential changes.

## Data quality rules

- Record source, observation time, product URL, seller and availability separately
  for every retailer. Never pass one store's data off as another store's offer.
- Distinguish a verified absence from a fetch failure or unknown result.
- Compare exact variants using EAN/SKU/model and relevant attributes. An uncertain
  match must remain unresolved for review.
- Preserve the prior value for the failing store and mark it stale or not live.
- Keep the public page honest about source and freshness; don't imply that cached
  data was just checked.

## Refresh operations

The live schedule currently comes from cron-job.org at 15-minute intervals in
`Europe/Madrid`. It calls the Vercel API with `source=automatic` and a bearer secret.
GitHub Actions also contains a scheduled trigger, but confirm actual runs in GitHub
Actions rather than assuming that a cron entry fired. See the root `README.md` for
operator setup and recovery steps.

Never print secret values. `GITHUB_ACTIONS_TOKEN` and `PRICE_CRON_SECRET` belong in
Vercel Production; the latter must match cron-job.org's Authorization header. An
HTTP 202 means GitHub accepted or already had an active run, not that scraping and
publication completed.

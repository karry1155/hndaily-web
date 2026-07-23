# HNHOT article enrichment V4.3

## Single semantic pass

Each article receives one grounded semantic response. Article detail, subject,
region, topic, event, plan and reader-reminder pages all consume that same JSON.
The publisher may validate, generate stable technical IDs, count, sort, group and
join values, but it may not create a competing semantic interpretation.

```text
source article
  -> prompts/article-enrichment/v4.3
       summary / scope
       subjects.activities
       locations / topics / events / plans
       reader_leads
  -> strict schema 13 validation
  -> deterministic public IDs and indexes
  -> content/
  -> site/
```

Subject actions belong directly to `subjects[].activities`; there is no generic
`observations` array. Region and topic pages reuse the station article title.
Event names and planning-document names are their page identities.

## Version boundaries

The repository root is the current application. Prompt packages may be versioned
inside `prompts/article-enrichment/`, and production responses are separated under
`data/runs/`. A prompt revision does not create a copied application or frontend.

Accepted code states are Git commits and release tags. Full historical directory
copies in `../hndaily-web-radar-snapshots/` are migration-only recovery material
and are never runtime dependencies.

## Responsive navigation

Desktop exposes the complete information architecture in the left sidebar:
reading pages, exploration pages and reader services. Mobile retains four stable
bottom destinations—front page, all reports, daily and more—and routes all
exploration and service pages through More.


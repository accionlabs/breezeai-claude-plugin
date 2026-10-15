# sources.json — Schema and Extraction Rules

## Schema

```json
{
  "REQ-001 Fund Upload": ["upload", "fund", "csv", "valuation date"],
  "REQ-002 Share Class Divergence": ["share class", "divergence", "bps", "threshold"],
  "US-007 User Login": ["login", "authentication", "password", "session"]
}
```

Key = exact section/requirement title. Value = 3–6 lowercase domain keywords.

## What to extract as keys

- Named requirements: `REQ-001: …`, `US-12: …`, `AC-03: …`
- Section headings that represent a feature, user story, or acceptance criterion
- Numbered bullets describing discrete system behaviour
- Table rows with requirement IDs and descriptions

If the page has only prose (no structured requirements), use H2/H3 headings as keys.

## Keyword rules

- 3–6 terms per requirement — domain nouns and verbs only
- Lowercase, no punctuation
- Omit stop words and generic CRUD verbs: create, update, delete, get, list, show, set
- Prefer domain-specific terms: entity names, status values, threshold labels, field names

## Full-text requirements list

Alongside `sources.json`, keep the raw requirement text for each key (one sentence or
short paragraph). This is used in Step 5 for semantic comparison against action
descriptions — it is NOT written to disk, just held in context.

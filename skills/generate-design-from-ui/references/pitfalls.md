# Common Pitfalls

| Pitfall                                       | Symptom                                   | Fix                                                                                   |
| --------------------------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------- |
| Reading only `index.tsx`                      | < 3 components per page                   | Glob the page dir, read 4-10 files                                                    |
| Skipping component drill-down                 | Wrapper components hide sub-components    | Follow import tree                                                                    |
| Inventing generic names instead of repo names | Design graph doesn't match codebase       | Use actual exported component names                                                   |
| Missing TEMPLATE                              | Page has no layout structure              | Mandatory for every Page                                                              |
| Skipping existingcomponents.json update       | Duplicate components                      | BLOCKING GATE                                                                         |
| Batching multiple scenarios                   | Low per-scenario quality                  | One bulk call per scenario                                                            |
| Classifying all components as ORGANISM        | Flat hierarchy                            | Use all atomic design levels                                                          |
| Naming templates after pages                  | Non-reusable templates                    | Name by layout pattern                                                                |
| Bulk-fetching functional graph                | Memory overflow                           | Fetch incrementally per scenario                                                      |
| Mapping step to BOTH Flow and Page            | Schema violation                          | Exclusive: Flow OR Page                                                               |
| Missing `scenarioId` link                     | Design graph disconnected from functional | Always include from fetched scenario                                                  |
| Guessing components from action names         | Misses real UI structure                  | Read actual JSX code                                                                  |
| Not fetching steps/actions                    | Missing stepIds/actionIds in payload      | Always call Get_all_steps_actions_for_a_scenario_id                                   |
| Orphaned stepIds/actionIds                    | Functional IDs not linked to design       | Every ID must appear in at least one design node                                      |
| Skipping Flow Registry check                  | Duplicate flows across scenarios          | LINK before CREATE — check (name, modality)                                           |
| Skipping Page Registry check                  | Duplicate pages across flows              | LINK before CREATE — check (name, pageType)                                           |
| Not updating Flow/Page registries post-upsert | Next scenario can't detect existing flows/pages | Write `existingflows.json` and `existingpages.json` to disk after every upsert        |
| Omitting reused flows from payload            | Orphaned UserJourneys with no flow        | Include reused flow by name with `pages: []` — backend dedup adds parent edge         |
| Omitting reused pages from payload            | Orphaned Flows with no page               | Include reused page by name with `components: []` — backend dedup adds parent edge    |
| Using `designSystemRef` as dedup key          | Backend ignores it for dedup              | Backend deduplicates by `projectUuid + name` (case-insensitive)                       |
| Skipping greps for same-page scenarios        | All scenarios get 1 flow / 1 page         | Run greps upfront (Step 3-upfront), analyze each scenario's actions against the cache |
| Using lowercase pageType/modality             | Backend rejects invalid enum values       | Always uppercase: `FORM`, `LIST`, `DETAIL`, `DASHBOARD`, `WEB`, `MOBILE`              |
| Adding `actionIds` to Page payloads           | Field doesn't exist on Page entity        | Actions map to Components only, not Pages                                             |

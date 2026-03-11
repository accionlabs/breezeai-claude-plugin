---
name: architecture
description: >
  Analyze system architecture using the code graph and documents.
  Identifies service boundaries, dependencies, tech stack, and
  patterns. Use when: "how is it architected", "service
  dependencies", "tech stack for X", planning features across
  services.
---

## Guard

Read `.breeze.json`. If missing, tell user to run `/breeze:init`.
Extract `apiKey` and `projectUuid`.

## Analysis Flow

### 1. Search Code Graph

Call `Code_Graph_Search` with architecture-relevant queries:

- Service/module names from $ARGUMENTS
- Broad queries like "controllers", "services", "middleware",
  "routes"

### 2. Search Documents

Call `Documents` for architecture docs, design decisions,
constraints, ADRs.

### 3. Map to Functional Capabilities

Call `Functional_Graph_Search` to correlate architecture components
with functional outcomes — understand which code serves which
business capability.

## Output Format

Present your analysis using this structure:

**Architecture Analysis: [Scope]**

**1. Component Overview**
Key services/modules, tech stack per component.

**2. Dependency Map**
Service-to-service, external integrations, shared libraries.

**3. Patterns Identified**
MVC, microservices, event-driven, data flow, auth approach.

**4. Functional Mapping**
Which outcomes map to which components, coverage gaps.

**5. Recommendations**
Risks, concerns, improvements.

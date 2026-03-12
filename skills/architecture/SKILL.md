---
name: architecture-analysis
description: analyze the requirement against the existing architectural graph which can be accessed using breezeAi mcp tools
---
# architecture-analysis


## Instructions

### Step 1:
initialize breeze and setup project and api-key.

### Step 2:
ask user to define the requirement or feature properly for architectural analysis.

### Step 3:
format given user requirement and search existing architectural graph using `Call_Green_architecture_Ontology` mcp tool to understand the current architecture.

### Step 4:
identify which architectural layers are impacted by the given requirement. The architectural graph has 8 layers:
- **UserExperience** — frontend/client-side components
- **ApiGateway** — API gateway, routing, auth, rate limiting
- **Services** — backend microservices/services
- **Agents** — AI/ML agents, orchestration
- **EventQueue** — message queues, event streaming
- **DataLake** — databases, data stores, vector DBs
- **ObservabilityMonitoring** — logging, monitoring, alerting
- **Infrastructure** — cloud infra, deployment, scaling

Check if the impacted layers already exist in the current architectural graph. If a new layer/component is detected, ask user for confirmation whether to add it or reuse an existing one.

### Step 5:
if any conflict is detected in the architectural graph (e.g., a service/component already exists for the given requirement), ask user if they want to update the existing component or create a new one. Identify inter-layer relationships that need to be created or updated (e.g., Services -> PUBLISHES_TO -> EventQueue, ApiGateway -> ROUTES_TO -> Services).

### Step 6:
now show the architectural graph for the requirement user has given in tabular format, organized by layer with relationships clearly shown.


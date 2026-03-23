---
name: analyze-architecture
description: analyze the requirement against the existing architectural graph which can be accessed using breezeAi mcp tools.
---
## Guard

Read `.breeze.json`. If missing, tell user to run `/breeze:setup-project`.
Extract `apiKey` and `projectUuid`.

# architecture-analysis

## Instructions

### Step 1:
initialize breeze and setup project and api-key.

### Step 2:
ask user to define the requirement or feature properly for architectural analysis. 

### Step 3:
format given user requirement and get all existing architectural graph using Get whole architecture Graph using mcp tool to understand the current architecture.

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
now show the architectural graph for the requirement user has given in tabular format. Show the complete metadata of each component (all fields and properties) for user confirmation.

### Step 6:
ask user to confirm if he want to change or add any metadata, update accordingly.
again show step 5 until user confirms that architecture model is correct to procced.

### Step 7: Update Architectural Graph
 after user confirms the architectural graph, save all new or updated components to the          architectural graph using create architecture node mcp tool following the layer hierarchy order. If user chose to update existing nodes in Step 5, use update architecture node mcp instead. Refer to `references/guide.md` for data model and required fields.    

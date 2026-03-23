### Architectural Graph

The architectural graph consists of 8 layers under a root `Architectural` node:

**Architectural → UserExperience / ApiGateway / Services / Agents / EventQueue / DataLake / ObservabilityMonitoring / Infrastructure**

1. **UserExperience** - Frontend/client-side applications that users interact with
2. **ApiGateway** - API gateway layer handling routing, authentication, rate limiting
3. **Services** - Backend microservices implementing business logic
4. **Agents** - AI/ML agents for orchestration and intelligent processing
5. **EventQueue** - Message queues and event streaming infrastructure
6. **DataLake** - Databases, data stores, vector databases
7. **ObservabilityMonitoring** - Logging, monitoring, alerting, and observability
8. **Infrastructure** - Cloud infrastructure, deployment, and scaling

---

### Metadata Priority Rule

When populating component metadata, **prefer the fields defined below for each layer first**. These are the standard metadata fields per layer. Only accept or add extra metadata fields if the user explicitly provides them separately. Do not invent or assume additional fields beyond the layer-specific ones unless the user requests it.

---

### Data Model Samples

#### 1. Architectural (Root)
The root node representing the entire architecture for a project.

```json
{
  "id": "arch-001",
  "projectId": "123",
  "projectUuid": "b2e9826d-5a94-4672-8af1-f1f80d5eb738",
  "name": "Architectural",
  "status": "active"
}
```

**Key fields:**
- `id` — Unique identifier
- `projectUuid` — Links to the project
- `status` — active/inactive

---

#### 2. UserExperience
Frontend/client applications.

```json
{
  "id": "ux-001",
  "architecturalId": "arch-001",
  "projectUuid": "b2e9826d-5a94-4672-8af1-f1f80d5eb738",
  "name": "Web Dashboard",
  "level": 1,
  "category": "frontend",
  "protocols": ["HTTPS"],
  "technologies": ["React", "TypeScript"],
  "pattern": ["SPA"],
  "emits_events": false,
  "metrics": ["page_load_time"],
  "description": "Main web dashboard for users",
  "repository_url": "https://github.com/org/frontend",
  "access_url": "https://app.example.com",
  "deployment": "Vercel"
}
```

**Key fields:**
- `architecturalId` — Links to parent Architectural node
- `name` — Component name
- `technologies` — Tech stack used
- `pattern` — Architecture patterns (SPA, SSR, etc.)

---

#### 3. ApiGateway
API gateway handling routing and authentication.

```json
{
  "id": "apigw-001",
  "architecturalId": "arch-001",
  "projectUuid": "b2e9826d-5a94-4672-8af1-f1f80d5eb738",
  "name": "Main API Gateway",
  "level": 2,
  "category": "gateway",
  "pattern": ["API Gateway"],
  "protocols": ["REST", "WebSocket"],
  "technologies": ["Kong", "Node.js"],
  "capabilities": ["routing", "rate-limiting", "auth"],
  "auth_methods": ["JWT", "OAuth2"],
  "rate_limit": "1000/min",
  "emits_events": true,
  "metrics": ["request_count", "latency_p99"],
  "description": "Central API gateway",
  "deployment": "Kubernetes"
}
```

**Key fields:**
- `capabilities` — Gateway capabilities
- `auth_methods` — Supported authentication methods
- `rate_limit` — Rate limiting configuration

---

#### 4. Services
Backend microservices.

```json
{
  "id": "svc-001",
  "architecturalId": "arch-001",
  "projectUuid": "b2e9826d-5a94-4672-8af1-f1f80d5eb738",
  "name": "User Service",
  "level": 3,
  "category": "microservice",
  "pattern": ["CQRS", "Event Sourcing"],
  "technologies": ["Node.js", "TypeScript", "Express"],
  "emits_events": true,
  "domain": ["user-management"],
  "deployment": "Kubernetes",
  "protocols": ["REST", "gRPC"],
  "metrics": ["request_latency", "error_rate"],
  "description": "Handles user CRUD and authentication",
  "repository_url": "https://github.com/org/user-service",
  "access_url": "http://user-service:3000"
}
```

**Key fields:**
- `domain` — Business domain this service belongs to
- `emits_events` — Whether this service publishes events
- `pattern` — Architecture patterns used

---

#### 5. Agents
AI/ML agents for orchestration.

```json
{
  "id": "agent-001",
  "architecturalId": "arch-001",
  "projectUuid": "b2e9826d-5a94-4672-8af1-f1f80d5eb738",
  "name": "Classification Agent",
  "level": 3,
  "category": "ai-agent",
  "pattern": ["ReAct", "Chain-of-Thought"],
  "technologies": ["Python", "LangChain"],
  "model_backend": "Claude",
  "tools_available": ["search", "classify"],
  "emits_events": true,
  "metrics": ["inference_latency", "accuracy"],
  "description": "Classifies incoming requests",
  "access_url": "http://agent-service:8000",
  "protocols": ["REST"],
  "deployment": "Kubernetes"
}
```

**Key fields:**
- `model_backend` — LLM backend used
- `tools_available` — Tools the agent can invoke

---

#### 6. EventQueue
Message queues and event streaming.

```json
{
  "id": "eq-001",
  "architecturalId": "arch-001",
  "projectUuid": "b2e9826d-5a94-4672-8af1-f1f80d5eb738",
  "name": "Order Events Queue",
  "level": 4,
  "category": "message-queue",
  "pattern": ["Pub/Sub"],
  "technologies": ["Kafka"],
  "protocols": ["AMQP"],
  "emits_events": true,
  "metrics": ["throughput", "consumer_lag"],
  "description": "Handles order-related events",
  "access_url": "kafka://broker:9092",
  "deployment": "Kubernetes"
}
```

---

#### 7. DataLake
Databases and data stores.

```json
{
  "id": "dl-001",
  "architecturalId": "arch-001",
  "projectUuid": "b2e9826d-5a94-4672-8af1-f1f80d5eb738",
  "name": "Primary PostgreSQL",
  "level": 5,
  "category": "relational-db",
  "pattern": ["Master-Replica"],
  "technologies": ["PostgreSQL"],
  "model_type": "relational",
  "vector_db": "",
  "emits_events": false,
  "metrics": ["query_latency", "connections"],
  "description": "Primary relational database",
  "access_url": "postgresql://db:5432",
  "deployment": "AWS RDS"
}
```

**Key fields:**
- `model_type` — Database model type (relational, document, graph, etc.)
- `vector_db` — Vector database engine if applicable

---

#### 8. ObservabilityMonitoring
Monitoring and observability.

```json
{
  "id": "obs-001",
  "architecturalId": "arch-001",
  "projectUuid": "b2e9826d-5a94-4672-8af1-f1f80d5eb738",
  "name": "Monitoring Stack",
  "level": 6,
  "category": "observability",
  "pattern": ["OpenTelemetry"],
  "technologies": ["Prometheus", "Grafana", "Jaeger"],
  "alert_channels": ["Slack", "PagerDuty"],
  "pillers": ["metrics", "traces", "logs"],
  "emits_events": false,
  "metrics": ["uptime", "alert_count"],
  "self_monitored": true,
  "description": "Centralized monitoring and alerting",
  "access_url": "https://grafana.example.com",
  "deployment": "Kubernetes"
}
```

**Key fields:**
- `pillers` — Observability pillars (metrics, traces, logs)
- `alert_channels` — Alert notification channels
- `self_monitored` — Whether the monitoring system monitors itself

---

#### 9. Infrastructure
Cloud infrastructure and deployment.

```json
{
  "id": "infra-001",
  "architecturalId": "arch-001",
  "projectUuid": "b2e9826d-5a94-4672-8af1-f1f80d5eb738",
  "name": "AWS Production Cluster",
  "level": 7,
  "category": "cloud",
  "pattern": ["Multi-AZ"],
  "technologies": ["AWS EKS", "Terraform"],
  "cloud_provider": "AWS",
  "regions": ["us-east-1", "eu-west-1"],
  "deployment_model": "Kubernetes",
  "node_count": 12,
  "cpu_cores_total": 96,
  "storage_pb": 2,
  "scalability": "horizontal",
  "backup_frequency": "daily",
  "emits_events": false,
  "metrics": ["cpu_utilization", "memory_usage"],
  "description": "Production Kubernetes cluster on AWS"
}
```

**Key fields:**
- `cloud_provider` — Cloud provider
- `regions` — Deployment regions
- `deployment_model` — Deployment strategy
- `scalability` — Scaling approach

---


### MCP Tools Mapping

| Operation | Tool |
|-----------|------|
| Full architecture analysis | `Get_All_architecture_Graph` |
| get architectural components by label | `Get_Architecture_Nodes_By_Label` |
| Setup project/workspace | `Breeze_Workspace_Setup` |
| Get project details | `Call_Get_Project_Details_` |
| Update architectural graph | `Update_Architecture_Node` |
| Create architectural graph | `Create_Architecture_Node` |

---

### Layer Levels (Data Flow Order)

| Level | Layer | Role |
|-------|-------|------|
| 1 | UserExperience | Client-facing frontends |
| 2 | ApiGateway | Request routing & auth |
| 3 | Services / Agents | Business logic & AI |
| 4 | EventQueue | Async messaging |
| 5 | DataLake | Data persistence |
| 6 | ObservabilityMonitoring | System health |
| 7 | Infrastructure | Cloud & deployment |

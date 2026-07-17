# IaC → Architecture layer mapping

Terraform / IaC is the **authoritative source for provisioned infrastructure**
(Infrastructure, EventQueue, DataLake, ApiGateway) — a spec doc is usually vaguer
about them than the code that actually provisions them.

**Why a direct read, not the code ontology:** the Breeze code-ontology generator
only parses *source languages* (JS/TS/Python/Java/Go/C#/PHP/Perl…). It never turns
`.tf` / HCL into code nodes, so `Code_Graph_Search` returns nothing structured for
a Terraform repo. The only reliable path is a filesystem read (Read/Glob/Grep) of
the `.tf` files, parsing `resource` and `module` blocks directly.

## How to read a Terraform repo

1. `Glob` for `**/*.tf` (and `**/*.tf.json`, `**/*.hcl`). Skip `.terraform/`,
   `**/.git/`, vendored modules.
2. For each file, extract `resource "<type>" "<name>" { ... }` and
   `module "<name>" { source = ... }` blocks. Capture the type, local name, and
   the salient args (engine, instance_class, region, `tags`, `name`/`bucket`,
   `topic`/`queue` names).
3. Resolve `module` calls to their source (local path or registry) — a module
   usually provisions a themed bundle (e.g. an `eks` module → Infrastructure +
   Services workloads). Read the module's own `.tf` if it's a local path.
4. Read `provider` blocks + `*.tfvars` / `locals` for cloud provider, region(s),
   and environment — set these on the resulting nodes.
5. **`terraform state` / plan output, if the user provides it, is even better** —
   it resolves interpolations and counts. Prefer it when available; otherwise the
   static `.tf` parse is sufficient for topology.

## Resource → layer mapping

Match on resource-type prefix. When a type isn't listed, infer from its role, or
flag it for the Phase 6 gate rather than guessing.

### AWS

| Resource type (prefix) | Layer | Notes |
|---|---|---|
| `aws_sqs_queue`, `aws_sns_topic`, `aws_msk_cluster`, `aws_kinesis_stream`, `aws_kinesis_firehose`, `aws_mq_broker` | **EventQueue** | `technologies`: SQS/SNS/Kafka(MSK)/Kinesis/MQ |
| `aws_rds_*`, `aws_db_instance`, `aws_aurora_*`, `aws_dynamodb_table`, `aws_elasticache_*`, `aws_redshift_*`, `aws_opensearch_domain`, `aws_s3_bucket` (data), `aws_timestream_*` | **DataLake** | set `model_type` (relational / document / warehouse / cache / search); `vector_db` if OpenSearch/pgvector used for embeddings |
| `aws_sagemaker_*`, `aws_bedrock_*`, `aws_glue_*` (ETL), EMR/`aws_emr_*` | **DataLake** (AI-ML / analytics) | Glue/EMR = analytics pipelines; SageMaker/Bedrock endpoints may also imply **Agents** — flag for user |
| `aws_api_gateway_*`, `aws_apigatewayv2_*`, `aws_lb`/`aws_alb` (L7), `aws_appsync_*` | **ApiGateway** | `auth_methods` from authorizer blocks; `rate_limit` from usage plans/throttle settings |
| `aws_lambda_function`, `aws_ecs_service`, `aws_ecs_task_definition`, `aws_apprunner_service` | **Services** | the *workload*; the cluster/VPC it runs on → Infrastructure |
| `aws_eks_cluster`, `aws_eks_node_group`, `aws_ecs_cluster`, `aws_vpc`, `aws_subnet`, `aws_autoscaling_group`, `aws_cloudfront_distribution` (CDN), `aws_route53_*`, `aws_instance`, `aws_elb`/`aws_lb` (L4) | **Infrastructure** | set `cloud_provider=AWS`, `regions`, `deployment_model`, `scalability` |
| `aws_cloudwatch_*`, `aws_xray_*`, `aws_prometheus_*` (AMP), `aws_grafana_*` (AMG) | **ObservabilityMonitoring** | `pillers`, `alert_channels` from SNS/PagerDuty targets |
| `aws_amplify_*`, `aws_s3_bucket` fronting `aws_cloudfront` as a static site | **UserExperience** | only when clearly a client app host, not data storage |

### GCP (`google_*`) / Azure (`azurerm_*`) — same roles

| Signal | Layer |
|---|---|
| `google_pubsub_*`, `azurerm_servicebus_*`, `azurerm_eventhub_*` | EventQueue |
| `google_sql_*`, `google_bigtable_*`, `google_bigquery_*`, `google_storage_bucket`, `azurerm_cosmosdb_*`, `azurerm_*_database`, `azurerm_storage_account`, `azurerm_synapse_*` | DataLake |
| `google_api_gateway_*`, `google_compute_*_load_balancer`, `azurerm_api_management`, `azurerm_application_gateway` | ApiGateway |
| `google_cloud_run_*`, `google_cloudfunctions_*`, `azurerm_function_app`, `azurerm_container_app` | Services |
| `google_container_cluster` (GKE), `google_compute_network`, `azurerm_kubernetes_cluster` (AKS), `azurerm_virtual_network` | Infrastructure |
| `google_monitoring_*`, `azurerm_monitor_*`, `azurerm_application_insights` | ObservabilityMonitoring |
| `google_vertex_ai_*`, `azurerm_cognitive_*`, `azurerm_machine_learning_*` | DataLake (AI-ML) / Agents (flag) |

### Kubernetes / Helm (`kubernetes_*`, `helm_release`)

- `kubernetes_deployment` / `kubernetes_stateful_set` / `helm_release` (an app chart) → **Services** (workload). Read the release `name`/chart to name it.
- `kubernetes_service` type `LoadBalancer` / `kubernetes_ingress*` → **ApiGateway**.
- The cluster itself → **Infrastructure**.
- A chart like `kafka`, `rabbitmq`, `redis` → **EventQueue** (Kafka/RabbitMQ) or **DataLake** (Redis-as-cache) by role.

## Merge policy with the spec doc

- **IaC is authoritative for provisioned infra** — Infrastructure, EventQueue,
  DataLake, ApiGateway node existence + tech + region come from Terraform.
- **Spec doc is authoritative for business-facing meaning** — Services domains,
  Agent purpose/`model_backend`/`tools_available`, UX modalities, descriptions.
- When both name the same thing (e.g. spec "Orders DB" ↔ `aws_rds_instance.orders`),
  **merge into one node**: spec supplies name/description/domain, IaC supplies
  technology/deployment/region/`access_url`.
- IaC surfaces a resource the spec omitted → add it flagged `source: "iac-discovered"`
  for the user to accept in the Phase 6 gate.
- Set `citation` on IaC-derived nodes to the `.tf` file path (+ resource address,
  e.g. `infra/modules/db/main.tf → aws_rds_instance.orders`).
- IaC-derived nodes carry **no `code_ontology_id`** (HCL isn't in the code graph) —
  that is expected. A Service node can still get its `code_ontology_id` from the
  application-code grounding pass (Phase 4) even when IaC provided its deployment
  fields.

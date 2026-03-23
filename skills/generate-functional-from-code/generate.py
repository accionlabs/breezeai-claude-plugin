"""
LangGraph Functional Graph Generator v2 — Three-Pass Pipeline
==============================================================
Pass 1: Extract intents from all clusters (Haiku, automated)
Pass 2: Create global structure (Sonnet, user approval)
Pass 3: Create scenarios per cluster (Sonnet, user approval per cluster)

Usage:
    python langgraph_fg_v2.py
    python langgraph_fg_v2.py --project-uuid <uuid> --api-key <key>
"""

import json
import os
import re
import sys
import time
import argparse
import logging
from pathlib import Path

import boto3
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_API_BASE = "https://isometric-backend.accionbreeze.com"
AUTH_HEADER_NAME = "api-key"
BREEZE_CONFIG_FILE = ".breeze.json"

# Defaults — overridden by .breeze.json, env vars, or CLI args
DEFAULT_AWS_REGION = "us-west-2"
DEFAULT_HAIKU_MODEL = "anthropic.claude-3-5-haiku-20241022-v1:0"
DEFAULT_SONNET_MODEL = "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-3-5-sonnet-20240620-v1:0"
MAX_TOKENS = 8192

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# API Client
# ---------------------------------------------------------------------------

class BreezeAPI:
    def __init__(self, api_base: str, api_key: str):
        self.api_base = api_base.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({AUTH_HEADER_NAME: api_key, "Content-Type": "application/json"})

    def get_ontologies(self, project_uuid):
        return self._get("/code-ontology/", {"filters[projectUuid][$eq]": project_uuid, "page": 1, "limit": 50}).get("data", [])

    def get_clusters(self, project_uuid, code_ontology_id):
        all_c = []
        page = 1
        while True:
            r = self._get("/code-cluster", {"filters[projectUuid][$eq]": project_uuid, "filters[codeOntologyId][$eq]": code_ontology_id, "page": str(page), "limit": "500", "sortName": "createdAt", "sortOrder": "asc"})
            items = r.get("data", [])
            all_c.extend(items)
            if page * 500 >= r.get("total", 0) or not items:
                break
            page += 1
        return all_c

    def get_cluster_files(self, project_uuid, cluster_id):
        all_f = []
        page = 1
        while True:
            r = self._get(f"/code-ontology/{project_uuid}/File", {"filters[clusterId][$in]": str(cluster_id), "children": "true", "page": str(page), "limit": "100", "sortName": "path", "sortOrder": "asc"})
            items = r.get("data", [])
            all_f.extend(items)
            if page * 100 >= r.get("total", 0) or not items:
                break
            page += 1
        return all_f

    def get_personas(self, project_uuid):
        return self._get(f"/functional-graph/{project_uuid}/Persona", {"page": "1", "limit": "50", "sortName": "persona", "sortOrder": "asc"}).get("data", [])

    def semantic_search(self, project_uuid, query, labels=None, limit=10):
        body = {"query": query, "limit": limit, "filters": {"projectUuid": {"$eq": project_uuid}}}
        if labels:
            body["includeLabels"] = labels
        r = self._post("/functional-graph/v2/semantic-search-filters?llmPlatform=AWSBEDROCK", body)
        return r.get("data", {}).get("results", {}).get("items", [])

    def code_graph_search(self, project_uuid, query, limit=5):
        return self.semantic_search(project_uuid, query, labels=["File", "Function", "Class"], limit=limit)

    def upsert(self, project_uuid, personas):
        body = {
            "payload": {"personas": personas},
            "project": {"uuid": project_uuid, "name": "projectA"},
            "skipStepAndAction": True,
        }
        log.info(f"  Upsert payload: {len(json.dumps(body))} bytes, {len(personas)} personas")
        return self._post("/functional-graph/upsert?embedding=true&llmPlatform=AWSBEDROCK", body)

    def _get(self, path, params=None):
        for attempt in range(3):
            try:
                r = self.session.get(f"{self.api_base}{path}", params=params, timeout=300)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                if attempt < 2: time.sleep(5)
                else: raise

    def _post(self, path, body):
        for attempt in range(3):
            try:
                r = self.session.post(f"{self.api_base}{path}", json=body, timeout=300)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                if attempt < 2: time.sleep(5)
                else: raise


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------

class LLM:
    def __init__(self, access_key, secret_key, region=DEFAULT_AWS_REGION):
        self.client = boto3.client("bedrock-runtime", region_name=region,
            aws_access_key_id=access_key, aws_secret_access_key=secret_key)
        self.default_model = DEFAULT_HAIKU_MODEL

    _call_count = 0

    def call(self, system, user, max_tokens=MAX_TOKENS, model=None):
        LLM._call_count += 1
        call_id = LLM._call_count

        # Log context being sent
        sys_tokens = len(system) // 4  # rough estimate
        usr_tokens = len(user) // 4
        log.info(f"  [LLM Call #{call_id}] System: ~{sys_tokens} tokens | User: ~{usr_tokens} tokens | Total: ~{sys_tokens + usr_tokens} tokens")

        # Write full context to log file for inspection
        log_dir = os.path.join(os.getcwd(), "llm_logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"call_{call_id:03d}.txt")
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"=== LLM CALL #{call_id} ===\n")
            f.write(f"Model: {model or BEDROCK_MODEL_ID}\n")
            f.write(f"Max tokens: {max_tokens}\n")
            f.write(f"System prompt tokens (est): ~{sys_tokens}\n")
            f.write(f"User prompt tokens (est): ~{usr_tokens}\n")
            f.write(f"\n{'='*60}\n")
            f.write(f"SYSTEM PROMPT:\n")
            f.write(f"{'='*60}\n")
            f.write(system)
            f.write(f"\n\n{'='*60}\n")
            f.write(f"USER PROMPT:\n")
            f.write(f"{'='*60}\n")
            f.write(user)

        body = json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": max_tokens,
            "system": system, "messages": [{"role": "user", "content": user}]})
        for attempt in range(3):
            try:
                r = self.client.invoke_model(modelId=model or self.default_model, body=body,
                    contentType="application/json", accept="application/json")
                response_text = json.loads(r["body"].read())["content"][0]["text"]

                # Log response
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"\n\n{'='*60}\n")
                    f.write(f"RESPONSE:\n")
                    f.write(f"{'='*60}\n")
                    f.write(response_text)

                log.info(f"  [LLM Call #{call_id}] Response: ~{len(response_text) // 4} tokens | Logged to: {log_file}")
                return response_text
            except Exception as e:
                if attempt < 2: log.warning(f"LLM retry {attempt+1}: {e}"); time.sleep(5)
                else: raise

    def call_json(self, system, user, max_tokens=MAX_TOKENS, model=None):
        raw = self.call(system, user, max_tokens, model)
        m = re.search(r'\[[\s\S]*\]|\{[\s\S]*\}', raw)
        if m:
            return json.loads(m.group())
        log.warning(f"  Failed to parse JSON from LLM response: {raw[:200]}")
        return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_summary(files):
    """Format cluster files with enough detail for intent extraction.
    Includes: path, classes with methods, standalone functions,
    route decorators, injected services, key calls."""
    lines = []
    for f in files:
        p = f.get("path", "?")
        loc = f.get("loc", 0)
        repo = f.get("repositoryName", "?")
        parts = [f"{p} ({loc} LOC, {repo})"]

        # Classes with methods
        for cls in f.get("classes", []):
            cname = cls.get("name", "?")
            ctype = cls.get("type", "class")
            if ctype == "interface":
                parts.append(f"  Interface: {cname}")
                continue
            parts.append(f"  Class: {cname}")

            # Injected services (from class statements with @Inject)
            for st in cls.get("statements", []):
                if isinstance(st, dict):
                    text = st.get("text", "")
                    stype = st.get("type", "")
                    # Route decorators
                    if stype == "decorator" and any(d in text for d in ["@Get", "@Post", "@Put", "@Delete", "@Patch"]):
                        route = text.replace("\r\n", " ").replace("\n", " ")[:150]
                        parts.append(f"    {route}")
                    # Injected services
                    elif "Inject" in text:
                        inject = text.replace("\r\n", " ").replace("\n", " ")[:100]
                        parts.append(f"    {inject}")

            # Methods
            for m in cls.get("methods", []):
                mname = m.get("name", "?")
                params = ", ".join(m.get("params", []))
                # Extract call targets
                try:
                    calls = json.loads(m.get("calls", "[]")) if isinstance(m.get("calls"), str) else m.get("calls", [])
                    call_names = [c.get("name", "") for c in calls if isinstance(c, dict) and c.get("name")][:8]
                except:
                    call_names = []
                call_str = f" → calls {', '.join(call_names)}" if call_names else ""
                parts.append(f"    - {mname}({params}){call_str}")

        # Standalone functions
        for fn in f.get("functions", []):
            fname = fn.get("name", "?")
            params = ", ".join(fn.get("params", []))
            try:
                calls = json.loads(fn.get("calls", "[]")) if isinstance(fn.get("calls"), str) else fn.get("calls", [])
                call_names = [c.get("name", "") for c in calls if isinstance(c, dict) and c.get("name")][:8]
            except:
                call_names = []
            call_str = f" → calls {', '.join(call_names)}" if call_names else ""
            parts.append(f"  - {fname}({params}){call_str}")

        # File-level statements (route definitions, key configs)
        for st in f.get("statements", []):
            if isinstance(st, dict):
                text = st.get("text", "")
                stype = st.get("type", "")
                if stype in ("decorator", "query_statement") or "Cron" in text or "Schedule" in text:
                    parts.append(f"  [{stype}] {text[:150]}")

        lines.append("\n".join(parts))
    return "\n\n".join(lines)


def format_code(files):
    lines = []
    for f in files:
        p, loc, repo = f.get("path", "?"), f.get("loc", 0), f.get("repositoryName", "?")
        lines.append(f"{'='*60}\nFILE: {p}\nRepository: {repo} | LOC: {loc}\n")
        emb = f.get("embeddingText", "")
        if "Imports:" in emb:
            lines.append(f"Imports: {emb.split('Imports:')[1].split(chr(10))[0].strip()}")
        ext = f.get("externalImports", [])
        if ext: lines.append(f"External: {', '.join(ext)}")
        for cls in f.get("classes", []):
            lines.append(f"\nClass: {cls.get('name','?')} (Lines: {cls.get('startLine','?')}-{cls.get('endLine','?')})")
            for st in cls.get("statements", []):
                if isinstance(st, dict):
                    lines.append(f"  [{st.get('type','')}] {st.get('text','')[:200]}")
            for m in cls.get("methods", []):
                lines.append(f"  - {m.get('name','?')}({', '.join(m.get('params',[]))}) | Lines: {m.get('startLine','?')}-{m.get('endLine','?')}")
                try:
                    calls = json.loads(m.get("calls", "[]")) if isinstance(m.get("calls"), str) else m.get("calls", [])
                    cn = [c.get("name", "") for c in calls if isinstance(c, dict)]
                    if cn: lines.append(f"    Calls: {', '.join(cn[:10])}")
                except: pass
                for st in m.get("statements", []):
                    if isinstance(st, dict): lines.append(f"    [{st.get('startLine','?')}] {st.get('text','')[:200]}")
        for fn in f.get("functions", []):
            lines.append(f"\n- {fn.get('name','?')}({', '.join(fn.get('params',[]))}) | Lines: {fn.get('startLine','?')}-{fn.get('endLine','?')}")
            try:
                calls = json.loads(fn.get("calls", "[]")) if isinstance(fn.get("calls"), str) else fn.get("calls", [])
                cn = [c.get("name", "") for c in calls if isinstance(c, dict)]
                if cn: lines.append(f"  Calls: {', '.join(cn[:10])}")
            except: pass
            for st in fn.get("statements", []):
                if isinstance(st, dict): lines.append(f"  [{st.get('startLine','?')}] {st.get('text','')[:200]}")
        for st in f.get("statements", []):
            if isinstance(st, dict): lines.append(f"[{st.get('type','')}] ({st.get('startLine','?')}) {st.get('text','')[:200]}")
        lines.append("")
    return "\n".join(lines)


def get_hook_entity(path):
    name = path.split("/")[-1].replace(".ts", "").replace(".tsx", "")
    entity = re.sub(r"^use-?", "", name)
    entity = re.sub(r"-?service$", "", entity)
    return entity


def chunk_text(text, max_chars=60000):
    """Split text into chunks at file boundaries to stay under max_chars.
    Never splits mid-file."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    current = ""
    # Split on file section boundaries (lines starting with a path and LOC)
    sections = re.split(r'(?=\n\S+\.\w+ \(\d+ LOC)', text)

    for section in sections:
        if len(current) + len(section) > max_chars and current:
            chunks.append(current)
            current = section
        else:
            current += section

    if current:
        chunks.append(current)

    return chunks if chunks else [text]


_auto_approve = False

def ask_user(prompt_text):
    """Interactive feedback. Auto-approves if --auto-approve flag is set."""
    if _auto_approve:
        print(f"\n{prompt_text}")
        print("  [AUTO-APPROVED]")
        return "approve", None
    print(f"\n{prompt_text}")
    print("[A]pprove / [E]dit / [S]kip / [Q]uit")
    while True:
        choice = input("> ").strip().lower()
        if choice in ("a", "approve"): return "approve", None
        if choice in ("s", "skip"): return "skip", None
        if choice in ("q", "quit"): return "quit", None
        if choice in ("e", "edit"):
            feedback = input("Enter corrections: > ").strip()
            return "edit", feedback
        print("Invalid. Enter A/E/S/Q")


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

INTENT_SYSTEM = """You are a Functional Intent Extraction Agent. Extract HIGH-LEVEL FUNCTIONAL INTENTS from the given input.

A functional intent is a short business capability phrase — what a user or system can DO, not how the code works internally.

## PERSONA RESOLUTION
Prefix each intent with the persona. Resolve using precedence:
1. **Named human role** implied by business domain
   (e.g., Admin, Fund Manager, Compliance Officer, Media Analyst)
2. **Generic human role** when domain role cannot be determined → "User"
3. **External System** — trigger originates outside the application boundary
   (webhooks, partner APIs, inbound integrations)
4. **System** — ONLY if fully internal and automated, no human trigger.
   Covers: background jobs, queue workers, schedulers, cron tasks,
   internal automation pipelines, script-triggered API calls.

If the triggering actor is ambiguous, default to "User", not "System".

**Forbidden persona names — NEVER use:**
Developer, Engineer, Programmer, Architect, API, Service, Component,
Module, Worker, Backend, Frontend, Database, Controller, Handler, Repository

## RULES
1. Extract ONE intent per DISTINCT business capability found in the code.
   - Do NOT split one capability into multiple intents
   - Do NOT merge unrelated capabilities into one intent
   - Typical range: 2-6 intents per cluster
   - If only one capability exists, return just 1
   - If the cluster covers many distinct concerns, return up to 8
2. Each intent = "Persona: Capability phrase" (3-7 words, starts with verb)
3. If multiple functions/methods contribute to the SAME business capability,
   merge into ONE intent.
4. For code input: ask "What does this code enable a user or operator to do?"
5. For backend code with route decorators (@Get, @Post, etc.):
   derive the business capability from the route purpose, not the path.
6. For pure backend code (jobs, workers, event handlers with no UI trigger):
   use "System" as persona.
7. If input contains ONLY data models, schemas, configs, type definitions,
   or internal utilities with no user-facing behavior → return []

Return ONLY a JSON array: ["Persona: Intent phrase", ...]
"""

STRUCTURE_SYSTEM = """You are a Functional Graph Structure Agent.

Given ALL functional intents from a codebase, create the global Persona → Outcome hierarchy.
This is the SKELETON — scenarios will be added in a subsequent pass.

---

## PERSONA RULES (STRICT)

Resolve using precedence:
1. **Named human role** implied by business domain
   (e.g., Admin, Fund Manager, Compliance Officer, Media Analyst)
2. **Generic human role** when domain role cannot be determined
   → "User", "Customer", "Visitor"
3. **External System** — trigger originates outside the application boundary
   (webhooks, partner APIs, payment gateways, inbound integrations).
   Do NOT use for internal subsystems.
4. **System** — ONLY if the behavior is fully internal and automated
   with no human or external system initiating or consuming the outcome.
   Covers: background jobs, queue workers, schedulers, cron tasks,
   internal automation pipelines, script-triggered API calls.
   "System" does NOT mean "I cannot determine the actor."

**Resolution rules:**
- Merge similar roles (e.g., "Admin User" and "Administrator" → reuse one)
- If ambiguous between User and System: "Does a human make a real-time
  decision that causes this to run?" YES → human Persona, NO → System
- If ambiguous between System and External System: "Does the trigger
  originate outside this application's boundary?" YES → External System
- If truly ambiguous, default to "User", not "System"
- Use '/' for combined personas with identical behavior
  (e.g., "User / Admin") — treated as a single persona entry

**Forbidden Persona names — NEVER use:**
Developer, Engineer, Programmer, Architect, API, Service, Component,
Module, Worker, Backend, Frontend, Database, Controller, Handler, Repository

---

## OUTCOME RULES (REUSE-FIRST)

Outcomes represent **high-level business capabilities**, not technical
functions, API endpoints, or implementation details.

- Evaluate existing Outcomes FIRST (if provided)
- Prefer broader Outcomes over narrower ones
- Capture variation as future Scenarios, NOT new Outcomes
- Create new Outcome ONLY if none can logically contain the intent

**Good Outcome names:**
- "Manage Fund Allocations"
- "Monitor Compliance Status"
- "Generate Reports"
- "Manage Code Ontology"

**Bad Outcome names (anti-patterns):**
- "Handle API Requests" (technical, not business)
- "Process Database Queries" (implementation detail)
- "Render Components" (frontend implementation)
- "Generate Embeddings" (too granular — this is a step, not an outcome)

**Outcome quality checks:**
- Understandable by non-technical stakeholders
- Stable across implementation and code changes
- Broad enough to absorb future Scenarios
- If outcomes seem too granular, merge related ones

---

## CODE CONTEXT RULES

When intents come from code analysis:
- FRONTEND intents: Persona = the human user who interacts with the UI
- BACKEND serving UI intents: Persona = the human user who triggers the API
- PURE BACKEND intents (jobs, workers, automation): Persona = "System"
- Do NOT derive Outcomes from endpoint paths or function names
- Derive Outcomes from the business domain the code serves

---

## OUTPUT FORMAT (STRICT JSON)

[{"persona": "<name>", "outcomes": [{"outcome": "<high-level capability>", "intents": ["<which intents map here>"]}]}]

Output outcomes WITHOUT scenarios — scenarios will be added in a subsequent pass.
"""

SCENARIO_SYSTEM = """You are a Functional Graph Expansion Agent.

Your task is to create Scenarios under the PROVIDED Personas and Outcomes.

## STRICT CONSTRAINTS
- You CANNOT create new Personas. Use ONLY the provided personas.
- You CANNOT create new Outcomes. Use ONLY the provided outcomes.
- You CAN create new Scenarios under existing Outcomes.
- If the code doesn't fit any provided Outcome, return [].

---

## PERSONA RULES

Persona MUST represent the ACTOR OF INTENT — the human, system, or
external system that initiates, governs, or consumes the outcome.

**Forbidden Persona names — NEVER use:**
Developer, Engineer, Programmer, Architect, API, Service, Component,
Module, Worker, Backend, Frontend, Database, Controller, Handler, Repository

---

## SCENARIO RULES

A Scenario describes a **specific user or system flow** under an Outcome.
It should be testable — you can write acceptance criteria for it.
It should have a clear start and end.

- Reuse existing Scenario if flow is semantically similar
- Create new only for genuinely distinct interaction paths
- If two Scenarios share >70% of their steps, consider merging them
- Each Scenario MUST include a brief description

**Duplicate detection — these are the SAME flow:**
- "Create new X" vs "Add X" vs "Submit X form" → SAME
- "View X details" vs "Access X" vs "View comprehensive X" → SAME
- "Approve or reject X" vs "Confirm X" vs "Reject X" → SAME decision flow
- "Schedule X" vs "Select X location" → SAME flow

**For System Persona scenarios**, the description MUST describe the
internal processing behavior, NOT the UI that triggers it.
Good: "System processes embedding generation request, calls Bedrock API,
      stores vectors, and runs clustering."
Bad:  "Generate embeddings for code ontology."

---

## CODE CLUSTER HANDLING

When the input is a code cluster:

1. Determine the code layer:
   - FRONTEND (components, pages, hooks, event handlers)
   - BACKEND (controllers, services, repositories, middleware)
   - MIXED (both present — apply rules independently per layer)

2. **FRONTEND code:**
   - Map components/pages to Scenarios
   - Map event handlers to implied user interactions
   - Persona = the human user who interacts with this UI
   - Frontend event handlers represent user interactions:
     onDrop/onDragOver → drag-and-drop, onChange → form input,
     validation functions → input validation (generate BOTH happy + error scenarios),
     toast.error/success → user-visible feedback,
     useBlocker/beforeunload → navigation guard with confirmation

3. **BACKEND code serving UI** (CRUD controllers, REST endpoints):
   - Infer the user-facing flow that triggers these endpoints
   - Persona = the human user who triggers the API via a UI
   - Derive Scenarios from business domain, not endpoint paths

4. **BACKEND internal API** (callable by scripts, automations):
   - If a human configures/triggers it via UI elsewhere → human Persona
   - If internal automation triggers it → "System"
   - If external platform triggers it → "External System"

5. **PURE BACKEND** (scheduled jobs, workers, event handlers):
   - Persona = "System"
   - Scenarios describe the processing flow, not a user flow
   - Do NOT invent fictional UI interactions

---

## NO-OP RULE

Return [] if the input:
- Introduces no new Scenario
- Only elaborates on existing functionality
- Contains ONLY API endpoint definitions with no inferable business intent
- Contains ONLY internal utility/helper functions
- Contains ONLY data models, schemas, or type definitions

---

## ALREADY CREATED SCENARIOS (DO NOT DUPLICATE)
{existing_scenarios}

## OUTPUT FORMAT (STRICT JSON)
Return ONLY:
[]
OR
[{{"persona": "<from provided list>", "outcomes": [{{"outcome": "<from provided list>", "scenarios": [{{"scenario": "<name>", "description": "<brief>"}}]}}]}}]
"""

STEPS_SYSTEM = """You are a Functional Flow Structuring Agent.
Output ONLY a valid JSON array. No explanations.

---

## STEP RULES
- Steps are sequential stages within a Scenario
- Each Step is a distinct phase (not a repeat of the scenario name)
- Step name = short verb phrase describing the stage
- A Scenario typically has 3-8 Steps (max 10)
- Steps are ORDERED — they represent a sequence

---

## ACTION RULES (PERSONA-AWARE)

### HUMAN PERSONA actions (User, Admin, or any named role)
- Actions describe what the user PROVIDES, DECIDES, or OBSERVES
- Actions MUST be platform-agnostic — must work for web, mobile, CLI, or voice
- FORBIDDEN words: click, tap, swipe, hover, scroll, drag, drop, toggle,
  button, dropdown, modal, dialog, popup, panel, checkbox, radio, slider,
  tooltip, menu, sidebar, navbar, tab, icon
- USE intent verbs: Provide, Choose, Confirm, Review, Dismiss, Open, Close,
  Submit, Cancel, Specify, Indicate, Acknowledge, Request
- description = null, unless context specifies a constraint
  (e.g., "Minimum 20 characters", "Blocked until all files uploaded")

### SYSTEM PERSONA actions
- Actions describe single atomic internal operations
- description is REQUIRED on every System action. Provide one of:
  - Formula or calculation
  - Threshold or limit
  - Field names involved
  - Condition or branching logic
  - Error message
  - Data format or transformation
  - Input/output shape of the operation
- When context lacks a specific value, describe the operation's
  input → output contract instead of setting null
- null is acceptable ONLY for trivial glue actions (e.g., "Log completion")

### EXTERNAL SYSTEM PERSONA actions
- Actions describe single atomic API/integration operations
- description = endpoint, payload shape, or auth mechanism when known; otherwise null

### Quantity guidelines
- A Step typically has 1-5 Actions
- If more than 5, consider splitting the parent Step

---

## CONTEXT HANDLING

**Source code:** Translate code to functional language — never reproduce raw code.
Map: conditionals → business rules, queries → data operations,
calculations → formulas. Action descriptions must include actual field names,
thresholds, and error messages extracted from code.

**When context lists enumerable items** (columns, filters, file types, strategies),
include EVERY item as a separate action. Never summarize with "e.g." or "such as".

---

## OUTPUT FORMAT
[{"scenario": "<title>", "steps": [{"step": "<purpose>", "actions": [{"action": "<interaction>", "description": "<detail or null>"}]}]}]
"""


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Three-pass functional graph generator")
    parser.add_argument("--project-uuid")
    parser.add_argument("--api-key")
    parser.add_argument("--api-base")
    parser.add_argument("--aws-access-key")
    parser.add_argument("--aws-secret-key")
    parser.add_argument("--aws-region")
    parser.add_argument("--haiku-model")
    parser.add_argument("--sonnet-model")
    parser.add_argument("--cluster", type=int, help="Process only this cluster ID (for testing)")
    parser.add_argument("--auto-approve", action="store_true", help="Skip all approval prompts, auto-approve everything")
    args = parser.parse_args()

    # Load config: CLI args > .breeze.json > env vars > defaults
    try:
        config = json.load(open(BREEZE_CONFIG_FILE))
    except:
        config = {}

    project_uuid = args.project_uuid or config.get("projectUuid")
    api_key = args.api_key or config.get("apiKey")
    api_base = args.api_base or config.get("apiBase", DEFAULT_API_BASE)
    aws_access_key = args.aws_access_key or config.get("awsAccessKey") or os.environ.get("AWS_ACCESS_KEYID")
    aws_secret_key = args.aws_secret_key or config.get("awsSecretKey") or os.environ.get("AWS_SECRET_KEY")
    aws_region = args.aws_region or config.get("awsRegion") or os.environ.get("AWS_REGION", DEFAULT_AWS_REGION)
    haiku_model = args.haiku_model or config.get("bedrockHaikuModel", DEFAULT_HAIKU_MODEL)
    sonnet_model = args.sonnet_model or config.get("bedrockSonnetModel", DEFAULT_SONNET_MODEL)

    if not project_uuid or not api_key:
        print("Error: need --project-uuid and --api-key (or set in .breeze.json)")
        sys.exit(1)
    if not aws_access_key or not aws_secret_key:
        print("Error: need AWS credentials. Set via:")
        print("  --aws-access-key / --aws-secret-key")
        print("  or .breeze.json: awsAccessKey / awsSecretKey")
        print("  or env: AWS_ACCESS_KEYID / AWS_SECRET_KEY")
        sys.exit(1)

    global _auto_approve
    _auto_approve = args.auto_approve

    api = BreezeAPI(api_base, api_key)
    llm = LLM(aws_access_key, aws_secret_key, region=aws_region)
    llm.default_model = haiku_model

    # ======================================================================
    # PASS 1: Extract intents from all clusters
    # ======================================================================
    print(f"\n{'='*60}")
    print("PASS 1: Extracting intents from all clusters")
    print(f"{'='*60}\n")

    ontologies = api.get_ontologies(project_uuid)
    all_clusters = []
    for ont in ontologies:
        oid = ont.get("_id") or ont.get("id")
        clusters = api.get_clusters(project_uuid, str(oid))
        for c in clusters:
            c["_ontName"] = ont.get("name", "?")
        all_clusters.extend(clusters)

    # Filter: skip single-file clusters, optionally filter to specific cluster
    clusters_to_process = [c for c in all_clusters if c.get("fileCount", 0) >= 2]
    if args.cluster:
        clusters_to_process = [c for c in clusters_to_process if c.get("clusterId") == args.cluster]

    print(f"Total clusters: {len(all_clusters)}, processing: {len(clusters_to_process)}")

    all_intents = {}  # cluster_id → [intents]
    flat_intents = []  # all intents flattened

    for i, cluster in enumerate(clusters_to_process):
        cid = cluster.get("clusterId")
        fc = cluster.get("fileCount", 0)
        print(f"  [{i+1}/{len(clusters_to_process)}] Cluster {cid} ({fc} files, {cluster['_ontName']})...", end=" ")

        try:
            files = api.get_cluster_files(project_uuid, cid)
            if not files:
                print("empty")
                continue
            summary = format_summary(files)
            chunks = chunk_text(summary, max_chars=60000)

            if len(chunks) > 1:
                print(f"{len(files)} files, {len(summary)} chars → {len(chunks)} chunks")

            cluster_intents = []
            for ci, chunk in enumerate(chunks):
                if len(chunks) > 1:
                    print(f"    Chunk {ci+1}/{len(chunks)} ({len(chunk)} chars)...", end=" ")
                chunk_intents = llm.call_json(INTENT_SYSTEM, f"Extract intents:\n\n{chunk}")
                if chunk_intents:
                    cluster_intents.extend(chunk_intents)
                    if len(chunks) > 1:
                        print(f"{len(chunk_intents)} intents")
                elif len(chunks) > 1:
                    print("no-op")

            # Deduplicate intents within cluster
            cluster_intents = list(set(cluster_intents))
            if cluster_intents:
                all_intents[cid] = cluster_intents
                flat_intents.extend(cluster_intents)
                print(f"{len(cluster_intents)} intents")
            else:
                print("no-op")
        except Exception as e:
            print(f"error: {e}")

    print(f"\nTotal: {len(flat_intents)} intents from {len(all_intents)} clusters")

    if not flat_intents:
        print("\nNo intents extracted. Nothing to process.")
        print("\nThe repository has not been uploaded to the code graph yet.")
        print("Upload it by running:\n")
        print(f"  npx github:accionlabs/breeze-code-ontology-generator repo-to-json-tree \\")
        print(f"    --repo <path-to-your-repo> \\")
        print(f"    --out breezeai \\")
        print(f"    --upload \\")
        print(f"    --capture-statements \\")
        print(f"    --user-api-key {api_key} \\")
        print(f"    --uuid {project_uuid} \\")
        print(f"    --baseurl {args.api_base}")
        print(f"\nRequires Node.js 22+. Once uploaded, re-run this script.")
        return

    # ======================================================================
    # PASS 2: Create global structure (with user approval)
    # ======================================================================
    print(f"\n{'='*60}")
    print("PASS 2: Creating global Persona → Outcome structure")
    print(f"{'='*60}\n")

    # Fetch existing graph
    existing_personas = api.get_personas(project_uuid)
    existing_context = ""
    if existing_personas:
        existing_context = f"\nExisting Personas (REUSE): {json.dumps([p.get('persona') for p in existing_personas])}"

    # Deduplicate intents
    unique_intents = list(set(flat_intents))
    print(f"Unique intents: {len(unique_intents)}")
    for intent in sorted(unique_intents):
        print(f"  - {intent}")

    # Ask LLM to create global structure
    structure_prompt = f"""Create the global Persona → Outcome structure for this codebase.

ALL intents extracted from the codebase:
{json.dumps(unique_intents, indent=2)}

{existing_context}

Group related intents under broad outcomes. A typical project should have 5-8 outcomes max.
"""

    structure = llm.call_json(STRUCTURE_SYSTEM, structure_prompt, max_tokens=8192, model=sonnet_model)

    # Present to user
    print(f"\nProposed structure:")
    for p in structure:
        print(f"\n  Persona: {p.get('persona', '?')}")
        for o in p.get("outcomes", []):
            print(f"    Outcome: {o.get('outcome', '?')}")
            for intent in o.get("intents", []):
                print(f"      ← {intent}")

    # Feedback loop
    while True:
        action, feedback = ask_user("Review the proposed structure:")
        if action == "approve":
            break
        elif action == "edit":
            # Re-run with feedback
            structure = llm.call_json(STRUCTURE_SYSTEM,
                f"{structure_prompt}\n\nUser feedback on previous proposal:\n{feedback}\n\nRevise accordingly.",
                max_tokens=8192)
            print(f"\nRevised structure:")
            for p in structure:
                print(f"\n  Persona: {p.get('persona', '?')}")
                for o in p.get("outcomes", []):
                    print(f"    Outcome: {o.get('outcome', '?')}")
        elif action == "skip":
            print("Skipping structure creation.")
            return
        elif action == "quit":
            print("Quitting.")
            return

    # Upsert structure (personas + outcomes only)
    upsert_personas = []
    for p in structure:
        persona_obj = {"persona": p["persona"], "outcomes": []}
        for o in p.get("outcomes", []):
            persona_obj["outcomes"].append({"outcome": o["outcome"], "scenarios": []})
        upsert_personas.append(persona_obj)

    # Log payload for debugging
    upsert_log = os.path.join(os.getcwd(), "llm_logs", "upsert_pass2.json")
    os.makedirs(os.path.dirname(upsert_log), exist_ok=True)
    with open(upsert_log, "w") as f:
        json.dump({"payload": {"personas": upsert_personas}, "project": {"uuid": project_uuid, "name": "projectA"}, "skipStepAndAction": True}, f, indent=2)
    print(f"\n  Payload logged to: {upsert_log}")

    print("Upserting structure to API...")
    try:
        api.upsert(project_uuid, upsert_personas)
        print("  Done! Waiting 15s for embeddings...")
        time.sleep(15)
    except Exception as e:
        print(f"  Error: {e}")
        return

    # Build locked structure for Pass 3
    locked_personas = [p["persona"] for p in structure]
    locked_outcomes = {}
    for p in structure:
        for o in p.get("outcomes", []):
            locked_outcomes[o["outcome"]] = p["persona"]

    # ======================================================================
    # PASS 3: Create scenarios per OUTCOME (with user approval)
    # ======================================================================
    print(f"\n{'='*60}")
    print("PASS 3: Creating scenarios per outcome")
    print(f"{'='*60}\n")

    # Build outcome list with their personas and mapped intents
    outcome_list = []
    for p in structure:
        persona = p["persona"]
        for o in p.get("outcomes", []):
            outcome_list.append({
                "persona": persona,
                "outcome": o["outcome"],
                "intents": o.get("intents", []),
            })

    print(f"Processing {len(outcome_list)} outcomes:\n")
    for ol in outcome_list:
        print(f"  {ol['persona']} > {ol['outcome']} ({len(ol['intents'])} intents)")

    for i, outcome_info in enumerate(outcome_list):
        persona = outcome_info["persona"]
        outcome_name = outcome_info["outcome"]
        outcome_intents = outcome_info["intents"]

        print(f"\n{'='*60}")
        print(f"[{i+1}/{len(outcome_list)}] {persona} > {outcome_name}")
        print(f"{'='*60}")

        try:
            # ---- Step 3a: Find relevant files via Code Graph Search ----
            print(f"  Searching for relevant files...")

            # Search using persona + outcome name + each mapped intent
            # Include persona to differentiate "User: Manage Documents" from "System: Manage Documents"
            search_queries = [f"{persona} {outcome_name}"] + [
                intent for intent in outcome_intents[:5]
            ]

            found_files = {}  # path → {score, data}
            for query in search_queries:
                try:
                    results = api.code_graph_search(project_uuid, query, limit=10)
                    for r in results:
                        score = r.get("score", 0)
                        data = r.get("data", {})
                        path = data.get("path", "")
                        label = r.get("label", "")
                        if not path or score < 0.3:
                            continue
                        # File nodes: add directly
                        # Function/Class nodes: extract parent file path and add
                        if label in ("File", "Function", "Class"):
                            file_id = data.get("id", "") if label == "File" else ""
                            if path not in found_files or score > found_files[path]["score"]:
                                found_files[path] = {"score": score, "data": data, "label": label}
                except Exception as e:
                    log.warning(f"  Search failed for '{query}': {e}")

            # Sort by relevance score
            sorted_files = sorted(found_files.items(), key=lambda x: -x[1]["score"])
            top_files = sorted_files[:15]  # max 15 files per outcome

            if not top_files:
                print(f"  No relevant files found, skipping")
                continue

            print(f"  Found {len(top_files)} relevant files:")
            for path, info in top_files:
                print(f"    {info['score']:.2f} [{info.get('label','?')}] {path}")

            # ---- Step 3b: Fetch full file details ----
            # Deduplicate paths (Function/Class nodes share path with their parent File)
            unique_paths = list({path for path, _ in top_files})
            print(f"  Fetching details for {len(unique_paths)} unique files...")
            file_details = []
            fetched_paths = set()
            for path, info in top_files:
                if path in fetched_paths:
                    continue
                fetched_paths.add(path)
                try:
                    # For File nodes, use id directly. For Function/Class, search by path.
                    if info.get("label") == "File":
                        file_id = info["data"].get("id", "")
                        details = api._get(f"/code-ontology/{project_uuid}/File", {
                            "filters[id][$eq]": file_id,
                            "children": "true",
                        })
                    else:
                        # Function/Class node — fetch parent file by path
                        details = api._get(f"/code-ontology/{project_uuid}/File", {
                            "filters[path][$eq]": path,
                            "children": "true",
                        })
                    items = details.get("data", [])
                    if items:
                        file_details.append(items[0])
                except Exception as e:
                    log.warning(f"  Failed to fetch {path}: {e}")

            if not file_details:
                print(f"  Could not fetch file details, skipping")
                continue

            print(f"  Got details for {len(file_details)} files")

            # ---- Step 3c: Extract scenarios (Sonnet) ----
            summary_text = format_summary(file_details)
            summary_chunks = chunk_text(summary_text, max_chars=80000)

            if len(summary_chunks) > 1:
                print(f"  Code summary: {len(summary_text)} chars → {len(summary_chunks)} chunks")

            scenario_prompt = SCENARIO_SYSTEM.format(existing_scenarios="[]")
            scenario_prompt_with_files = scenario_prompt.replace(
                '"description": "<brief>"',
                '"description": "<brief>", "relevant_files": ["<path1>", "<path2>"]'
            )

            # Process each chunk and merge results
            all_chunk_results = []
            for ci, chunk in enumerate(summary_chunks):
                if len(summary_chunks) > 1:
                    print(f"    Chunk {ci+1}/{len(summary_chunks)} ({len(chunk)} chars)...")

                user_prompt = f"""Create ALL scenarios for the outcome "{outcome_name}" under persona "{persona}".

Be EXHAUSTIVE — capture every distinct user or system flow you can identify from this code.

LOCKED Persona: {persona}
LOCKED Outcome: {outcome_name}

Related intents:
{json.dumps(outcome_intents, indent=2)}

CODE (files relevant to this outcome, chunk {ci+1}/{len(summary_chunks)}):
{chunk}

For each scenario, include a "relevant_files" array listing the file paths
most relevant to that scenario (for detailed code analysis in the next step).
"""

                print(f"  Extracting scenarios...")
                chunk_result = llm.call_json(scenario_prompt_with_files, user_prompt, max_tokens=8192, model=sonnet_model)
                if chunk_result:
                    all_chunk_results.extend(chunk_result)

            # Merge chunk results — deduplicate scenarios by name
            if not all_chunk_results:
                result = []
            else:
                # Merge into single persona→outcome structure
                merged = {}
                for po in all_chunk_results:
                    pname = po.get("persona", "")
                    if pname not in merged:
                        merged[pname] = {"persona": pname, "outcomes": {}}
                    for oo in po.get("outcomes", []):
                        oname = oo.get("outcome", "")
                        if oname not in merged[pname]["outcomes"]:
                            merged[pname]["outcomes"][oname] = {"outcome": oname, "scenarios": {}}
                        for so in oo.get("scenarios", []):
                            sname = so.get("scenario", "")
                            if sname not in merged[pname]["outcomes"][oname]["scenarios"]:
                                merged[pname]["outcomes"][oname]["scenarios"][sname] = so
                # Convert back to list format
                result = []
                for pname, pdata in merged.items():
                    persona_obj = {"persona": pname, "outcomes": []}
                    for oname, odata in pdata["outcomes"].items():
                        outcome_obj = {"outcome": oname, "scenarios": list(odata["scenarios"].values())}
                        persona_obj["outcomes"].append(outcome_obj)
                    result.append(persona_obj)

            if not result or result == []:
                print(f"  No scenarios found")
                continue

            # ---- Step 3d: Generate steps/actions per scenario (Haiku, focused files) ----
            all_sc = []
            for po in result:
                for oo in po.get("outcomes", []):
                    for so in oo.get("scenarios", []):
                        all_sc.append({
                            "persona": po["persona"],
                            "scenario": so["scenario"],
                            "description": so.get("description", ""),
                            "relevant_files": so.get("relevant_files", []),
                        })

            # Build file index for lookup
            details_by_path = {f.get("path", ""): f for f in file_details}

            print(f"  Generating steps/actions for {len(all_sc)} scenarios...")
            for batch_start in range(0, len(all_sc), 2):
                batch = all_sc[batch_start:batch_start + 2]

                # Collect relevant files for this batch
                relevant_paths = set()
                for sc in batch:
                    for fp in sc.get("relevant_files", []):
                        relevant_paths.add(fp)

                # Get full code for relevant files
                if relevant_paths:
                    relevant_file_data = [details_by_path[p] for p in relevant_paths if p in details_by_path]
                else:
                    relevant_file_data = file_details[:5]  # fallback

                focused_code = format_code(relevant_file_data)
                if len(focused_code) > 50000:
                    print(f"    Warning: code context {len(focused_code)} chars, truncating to 50K")
                    focused_code = focused_code[:50000] + "\n... (truncated)"

                batch_info = json.dumps([{
                    "persona": s["persona"],
                    "scenario": s["scenario"],
                    "description": s["description"]
                } for s in batch], indent=2)

                try:
                    steps = llm.call_json(STEPS_SYSTEM,
                        f"Generate steps and actions for EACH scenario.\n\nScenarios:\n{batch_info}\n\nRelevant code (full detail):\n{focused_code}",
                        max_tokens=8192)
                    if isinstance(steps, list):
                        for sr in steps:
                            for po in result:
                                for oo in po.get("outcomes", []):
                                    for so in oo.get("scenarios", []):
                                        if so["scenario"] == sr.get("scenario"):
                                            so["steps"] = sr.get("steps", [])
                except Exception as e:
                    log.warning(f"  Steps failed for batch: {e}")

            # Convert relevant_files to citations and clean up
            for po in result:
                for oo in po.get("outcomes", []):
                    # Outcome-level citations: all files found for this outcome
                    oo["citations"] = [
                        {"reference": path, "name": path, "type": "code"}
                        for path, _ in top_files
                    ]
                    for so in oo.get("scenarios", []):
                        # Scenario-level citations: from relevant_files
                        rel_files = so.pop("relevant_files", [])
                        so["citations"] = [
                            {"reference": fp, "name": fp, "type": "code"}
                            for fp in rel_files
                        ]
                        # Steps/Actions citations: from the files used in 3d context
                        for step in so.get("steps", []):
                            step["citations"] = so["citations"]  # same files as scenario
                            for action in step.get("actions", []):
                                action["citations"] = so["citations"]

            # Present to user
            print(f"\n  Proposed scenarios for '{outcome_name}':")
            for po in result:
                for oo in po.get("outcomes", []):
                    for so in oo.get("scenarios", []):
                        steps_count = len(so.get("steps", []))
                        actions_count = sum(len(st.get("actions", [])) for st in so.get("steps", []))
                        print(f"    {so['scenario']} ({steps_count} steps, {actions_count} actions)")

            action, feedback = ask_user(f"Approve scenarios for '{outcome_name}'?")

            if action == "approve":
                api.upsert(project_uuid, result)
                print(f"  Upserted {len(all_sc)} scenarios. Waiting 15s for embeddings...")
                time.sleep(15)
            elif action == "edit":
                result2 = llm.call_json(scenario_prompt_with_files,
                    f"{user_prompt}\n\nUser feedback:\n{feedback}\n\nRevise accordingly.",
                    max_tokens=8192, model=sonnet_model)
                if result2:
                    print(f"  Revised:")
                    for po in result2:
                        for oo in po.get("outcomes", []):
                            for so in oo.get("scenarios", []):
                                print(f"    {so['scenario']}")
                    a2, _ = ask_user("Approve revised?")
                    if a2 == "approve":
                        # Clean relevant_files
                        for po in result2:
                            for oo in po.get("outcomes", []):
                                for so in oo.get("scenarios", []):
                                    so.pop("relevant_files", None)
                        api.upsert(project_uuid, result2)
                        print(f"  Upserted revised. Waiting 15s for embeddings...")
                        time.sleep(15)
            elif action == "skip":
                print(f"  Skipped '{outcome_name}'")
            elif action == "quit":
                print("Quitting.")
                break

        except Exception as e:
            print(f"  Error processing '{outcome_name}': {e}")

    # ======================================================================
    # Summary
    # ======================================================================
    print(f"\n{'='*60}")
    print("COMPLETE")
    print(f"{'='*60}")
    print(f"  Personas: {', '.join(locked_personas)}")
    print(f"  Outcomes processed: {len(outcome_list)}")
    print(f"  Clusters analyzed (Pass 1): {len(all_intents)}")
    print(f"  Total intents extracted: {len(flat_intents)}")


if __name__ == "__main__":
    main()

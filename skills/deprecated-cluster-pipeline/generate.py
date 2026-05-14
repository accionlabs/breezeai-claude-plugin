"""
LangGraph Functional Graph Generator v4 — Method-Level Pipeline
================================================================
v4 improvements over v3:
  - Pass 1: Method-level extraction with conditional branch visibility
  - Pass 1: Large files (>500 LOC) get per-method detail including branching logic
  - Pass 1: Decorator/route metadata extracted per method (view_config, request_method)
  - Pass 1: Statement-level context (flag checks, parameter conditionals) visible to LLM
  - Pass 1: Frontend route configs and workflow tabs extracted as structured metadata
  - All v3 improvements retained (flag-aware prompts, max-6 outcomes, multi-query search)

Pass 1:   Extract intents from all clusters (Sonnet, method-level detail)
Pass 1.5: Dedup intents (filter + normalize + embed + DBSCAN clustering)
Pass 2:   Create outcomes via cluster-based assignment (Sonnet, dedup + assign)
Pass 3:   Create scenarios per outcome (Sonnet)

Usage:
    python generate_v4.py
    python generate_v4.py --project-uuid <uuid> --api-key <key>
    python generate_v4.py --resume-from 2 --auto-approve
"""

import json
import os
import re
import sys
import time
import argparse
import logging
from pathlib import Path
from collections import defaultdict

import boto3
import requests
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_distances

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_API_BASE = "https://isometric-backend.accionbreeze.com"
AUTH_HEADER_NAME = "api-key"
BREEZE_CONFIG_FILE = ".breeze.json"

# Defaults — overridden by .breeze.json, env vars, or CLI args
DEFAULT_AWS_REGION = "us-west-2"
DEFAULT_HAIKU_MODEL = "anthropic.claude-3-5-sonnet-20240620-v1:0"
DEFAULT_SONNET_MODEL = "arn:aws:bedrock:us-west-2::foundation-model/anthropic.claude-3-5-sonnet-20240620-v1:0"
EMBEDDING_MODEL = "amazon.titan-embed-text-v2:0"
DEFAULT_DBSCAN_EPS = 0.20
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
        from botocore.config import Config
        bedrock_config = Config(read_timeout=300, connect_timeout=10, retries={"max_attempts": 3})
        self.client = boto3.client("bedrock-runtime", region_name=region,
            aws_access_key_id=access_key, aws_secret_access_key=secret_key,
            config=bedrock_config)
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
        log_dir = os.path.join(os.getcwd(), "llm_logs_v4")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"call_{call_id:03d}.txt")
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"=== LLM CALL #{call_id} ===\n")
            f.write(f"Model: {model or self.default_model}\n")
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
                r = self.client.invoke_model_with_response_stream(
                    modelId=model or self.default_model, body=body,
                    contentType="application/json", accept="application/json")
                # Collect streamed chunks
                chunks = []
                for event in r["body"]:
                    chunk = event.get("chunk")
                    if chunk:
                        chunk_data = json.loads(chunk["bytes"])
                        if chunk_data.get("type") == "content_block_delta":
                            chunks.append(chunk_data.get("delta", {}).get("text", ""))
                response_text = "".join(chunks)

                # Log response
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(f"\n\n{'='*60}\n")
                    f.write(f"RESPONSE:\n")
                    f.write(f"{'='*60}\n")
                    f.write(response_text)

                log.info(f"  [LLM Call #{call_id}] Response: ~{len(response_text) // 4} tokens | Logged to: {log_file}")
                time.sleep(3)  # throttle to avoid Bedrock rate limits
                return response_text
            except Exception as e:
                if attempt < 2: log.warning(f"LLM retry {attempt+1}: {e}"); time.sleep(5)
                else: raise

    def call_json(self, system, user, max_tokens=MAX_TOKENS, model=None):
        raw = self.call(system, user, max_tokens, model)
        m = re.search(r'\[[\s\S]*\]|\{[\s\S]*\}', raw)
        if m:
            text = m.group()
            try:
                return json.loads(text)
            except json.JSONDecodeError as e:
                log.warning(f"  JSON parse error: {e}. Attempting repair...")
                repaired = text

                # Fix 1: Remove trailing commas before } or ]
                repaired = re.sub(r',\s*([}\]])', r'\1', repaired)

                # Fix 2: Handle truncated strings (cut off mid-value)
                # Find last unclosed quote and truncate there
                in_string = False
                last_quote_pos = -1
                for ci, ch in enumerate(repaired):
                    if ch == '"' and (ci == 0 or repaired[ci-1] != '\\'):
                        in_string = not in_string
                        last_quote_pos = ci
                if in_string and last_quote_pos > 0:
                    # Truncated inside a string — close it and trim
                    repaired = repaired[:last_quote_pos] + '"'
                    log.info(f"  Closed truncated string at position {last_quote_pos}")

                # Fix 3: Remove trailing commas again (after string fix)
                repaired = re.sub(r',\s*([}\]])', r'\1', repaired)

                # Fix 4: Close unbalanced brackets/braces
                # Find last complete JSON object/array boundary
                open_brackets = repaired.count('[') - repaired.count(']')
                open_braces = repaired.count('{') - repaired.count('}')
                if open_brackets > 0 or open_braces > 0:
                    # Truncate to last complete object
                    last_complete = max(repaired.rfind('}'), repaired.rfind(']'))
                    if last_complete > 0:
                        repaired = repaired[:last_complete + 1]
                        # Re-count after truncation
                        open_brackets = repaired.count('[') - repaired.count(']')
                        open_braces = repaired.count('{') - repaired.count('}')
                        # Close remaining open brackets/braces in correct order
                        # Scan from end to determine proper closing order
                        closers = []
                        for ci in range(len(repaired) - 1, -1, -1):
                            if open_braces <= 0 and open_brackets <= 0:
                                break
                            if repaired[ci] == '{' and open_braces > 0:
                                closers.append('}')
                                open_braces -= 1
                            elif repaired[ci] == '[' and open_brackets > 0:
                                closers.append(']')
                                open_brackets -= 1
                        repaired += ''.join(closers)

                try:
                    result = json.loads(repaired)
                    log.info(f"  JSON repair successful (recovered {len(json.dumps(result))} chars)")
                    return result
                except json.JSONDecodeError as e2:
                    log.warning(f"  JSON repair failed: {e2}. Raw response length: {len(raw)}")
                    return []
        log.warning(f"  Failed to parse JSON from LLM response: {raw[:200]}")
        return []


# ---------------------------------------------------------------------------
# Pass cache — saves/loads intermediate results between passes
# ---------------------------------------------------------------------------

CACHE_DIR = os.path.join(os.getcwd(), "llm_logs_v4")

def _cache_path(pass_num):
    return os.path.join(CACHE_DIR, f"cache_v4_pass{pass_num}.json")

def save_pass_cache(pass_num, data):
    """Save pass results to cache file."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path(pass_num)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"  [Cache] Pass {pass_num} results saved to {path}", flush=True)

def load_pass_cache(pass_num):
    """Load cached pass results. Returns None if not found."""
    path = _cache_path(pass_num)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"  [Cache] Loaded Pass {pass_num} results from {path}", flush=True)
        return data
    return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_summary(files):
    """Format cluster files with METHOD-LEVEL detail for intent extraction.

    v4 enhancement: For large files (>500 LOC), extracts per-method detail
    including conditional branches, flag checks, and decorator metadata.
    This allows the LLM to see workflow variants (e.g., icflag=9 vs icflag=3)
    that were invisible in v2/v3 file-level summaries.

    Includes: path, classes with methods + decorators + branch analysis,
    standalone functions with branch analysis, route decorators, key statements.
    """
    lines = []
    for f in files:
        p = f.get("path", "?")
        loc = f.get("loc", 0)
        repo = f.get("repositoryName", "?")
        parts = [f"{p} ({loc} LOC, {repo})"]

        # Determine detail level based on file size
        # Large files get full method-level branch analysis
        detailed_mode = loc > 300

        # External imports (important for understanding framework)
        ext = f.get("externalImports", [])
        if ext:
            parts.append(f"  Imports: {', '.join(ext[:15])}")

        # Classes with methods
        for cls in f.get("classes", []):
            cname = cls.get("name", "?")
            ctype = cls.get("type", "class")
            if ctype == "interface":
                parts.append(f"  Interface: {cname}")
                continue

            # Class-level decorators (route_name, view_defaults, etc.)
            decorators = cls.get("decorators", [])
            if decorators:
                for dec in decorators:
                    dec_text = dec if isinstance(dec, str) else str(dec)
                    parts.append(f"  Class: {cname} {dec_text[:200]}")
                    break
            else:
                parts.append(f"  Class: {cname}")

            # Class-level statements (route decorators, injections)
            for st in cls.get("statements", []):
                if isinstance(st, dict):
                    text = st.get("text", "")
                    stype = st.get("type", "")
                    if stype == "decorator" and any(d in text for d in
                        ["@Get", "@Post", "@Put", "@Delete", "@Patch",
                         "@view_config", "@view_defaults", "route_name"]):
                        route = text.replace("\r\n", " ").replace("\n", " ")[:200]
                        parts.append(f"    {route}")
                    elif "Inject" in text:
                        inject = text.replace("\r\n", " ").replace("\n", " ")[:100]
                        parts.append(f"    {inject}")

            # Methods — with branch analysis for large files
            for m in cls.get("methods", []):
                mname = m.get("name", "?")
                if mname in ("__init__", "constructor"):
                    continue  # skip constructors, they rarely contain business logic
                params = ", ".join(m.get("params", []))
                method_loc = (m.get("endLine", 0) or 0) - (m.get("startLine", 0) or 0)

                # Extract call targets
                try:
                    calls = json.loads(m.get("calls", "[]")) if isinstance(m.get("calls"), str) else m.get("calls", [])
                    call_names = [c.get("name", "") for c in calls if isinstance(c, dict) and c.get("name")][:10]
                except:
                    call_names = []
                call_str = f" → calls {', '.join(call_names)}" if call_names else ""

                # Method decorators (view_config, request_method, etc.)
                method_decorators = m.get("decorators", [])
                dec_str = ""
                for md in method_decorators:
                    md_text = md if isinstance(md, str) else str(md)
                    if any(kw in md_text for kw in ["view_config", "request_method", "route_name",
                                                      "Get", "Post", "Put", "Delete", "Patch"]):
                        dec_str = f" [{md_text[:120]}]"
                        break

                parts.append(f"    - {mname}({params}){dec_str}{call_str} ({method_loc} lines)")

                # Branch analysis for methods in large files
                if detailed_mode and method_loc > 15:
                    branches = _extract_branches(m)
                    for branch in branches:
                        parts.append(f"      {branch}")

        # Standalone functions — with branch analysis for large files
        for fn in f.get("functions", []):
            fname = fn.get("name", "?")
            params = ", ".join(fn.get("params", []))
            fn_loc = (fn.get("endLine", 0) or 0) - (fn.get("startLine", 0) or 0)
            try:
                calls = json.loads(fn.get("calls", "[]")) if isinstance(fn.get("calls"), str) else fn.get("calls", [])
                call_names = [c.get("name", "") for c in calls if isinstance(c, dict) and c.get("name")][:10]
            except:
                call_names = []
            call_str = f" → calls {', '.join(call_names)}" if call_names else ""

            # Function decorators
            fn_decorators = fn.get("decorators", [])
            dec_str = ""
            for fd in fn_decorators:
                fd_text = fd if isinstance(fd, str) else str(fd)
                if any(kw in fd_text for kw in ["view_config", "request_method", "route_name",
                                                  "Get", "Post", "Put", "Delete", "Patch"]):
                    dec_str = f" [{fd_text[:120]}]"
                    break

            parts.append(f"  - {fname}({params}){dec_str}{call_str} ({fn_loc} lines)")

            if detailed_mode and fn_loc > 15:
                branches = _extract_branches(fn)
                for branch in branches:
                    parts.append(f"    {branch}")

        # File-level statements (route definitions, key configs, workflow configs)
        for st in f.get("statements", []):
            if isinstance(st, dict):
                text = st.get("text", "")
                stype = st.get("type", "")
                if stype in ("decorator", "query_statement") or "Cron" in text or "Schedule" in text:
                    parts.append(f"  [{stype}] {text[:150]}")
                # Catch frontend config objects (workflow tabs, route configs, createNewPath etc.)
                elif stype == "lexical_declaration" and any(kw in text for kw in
                    ["createNewPath", "route", "config", "tabs", "workflow", "icon:", "color:"]):
                    # Truncate but keep enough to see the structure
                    clean = text.replace("\r\n", " ").replace("\n", " ")[:300]
                    parts.append(f"  [config] {clean}")

        lines.append("\n".join(parts))
    return "\n\n".join(lines)


def _extract_branches(method_or_fn):
    """Extract conditional branches and flag checks from a method/function's statements.

    Looks for patterns like:
    - if/elif with flag checks (icflag, type, mode, status)
    - request parameter checks (request.params, request.matchdict)
    - request_param decorators
    - switch/case or match statements

    Returns a list of branch description strings.
    """
    branches = []
    statements = method_or_fn.get("statements", [])

    for st in statements:
        if not isinstance(st, dict):
            continue
        text = st.get("text", "")
        stype = st.get("type", "")

        # Skip empty or very short statements
        if len(text) < 10:
            continue

        clean = text.replace("\r\n", " ").replace("\n", " ").strip()

        # Conditional branches with flags/types/modes
        if stype in ("if_statement", "elif_clause", "else_clause", "conditional_expression"):
            # Look for meaningful business conditionals (not null checks or error handling)
            if any(kw in clean.lower() for kw in [
                "flag", "type", "mode", "status", "role", "kind", "category",
                "inout", "csflag", "gsflag", "icflag", "avflag", "maflag",
                "request_param", "request.params", "request.matchdict",
                "query.type", "query.mode", "wftype", "wf_type",
                "== 9", "== 3", "== 15", "== 19", "== 4", "== 16",
                "'sale'", "'purchase'", "'receipt'", "'payment'",
                "\"sale\"", "\"purchase\"", "\"receipt\"", "\"payment\"",
            ]):
                branches.append(f"BRANCH: {clean[:180]}")

        # Decorator-based routing (view_config with request_param)
        elif stype == "decorator":
            if "request_param" in clean or "request_method" in clean:
                branches.append(f"ROUTE: {clean[:180]}")

        # Query statements that reveal entity relationships
        elif stype == "query_statement":
            # Only include if it references key business tables/entities
            if any(kw in clean.lower() for kw in [
                "invoice", "voucher", "delchal", "purchaseorder", "transfernote",
                "rejectionnote", "customerandsupplier", "product", "godown",
                "stock", "tax", "bankrecon", "drcr", "budget", "project",
                # Generic table references for non-GNUKhata projects
                "insert", "update", "delete", "create", "where",
            ]):
                # Truncate but keep table/entity names visible
                branches.append(f"DB: {clean[:150]}")

    # Limit to most informative branches (avoid noise)
    if len(branches) > 8:
        # Prioritize BRANCH and ROUTE over DB
        priority = [b for b in branches if b.startswith("BRANCH:") or b.startswith("ROUTE:")]
        db = [b for b in branches if b.startswith("DB:")]
        branches = priority[:6] + db[:2]

    return branches


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


def format_search_results(intent, results):
    """Format code graph search results for an intent as lightweight context.
    Returns a compact summary suitable for scenario identification
    (no full file fetch needed)."""
    lines = [f"Intent: {intent}"]
    for r in results:
        score = r.get("score", 0)
        label = r.get("label", "")
        data = r.get("data", {})
        path = data.get("path", "")
        name = data.get("name", "")
        emb = data.get("embeddingText", "")
        # Truncate embedding text to first 300 chars for context
        if emb and len(emb) > 300:
            emb = emb[:300] + "..."
        lines.append(f"  [{label}] {path} | {name} (score: {score:.2f})")
        if emb:
            lines.append(f"    {emb}")
    return "\n".join(lines)


def chunk_text(text, max_chars=80000):
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


# ---------------------------------------------------------------------------
# Intent Dedup Helpers (Pass 1.5)
# ---------------------------------------------------------------------------

def normalize_intent(text):
    """Normalize intent text for dedup comparison."""
    if ": " in text:
        text = text.split(": ", 1)[1]
    text = text.lower()
    text = re.sub(r"\(.*?\)", "", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = " ".join(text.split())
    return text


def normalization_dedup(intents):
    """Merge intents that become identical after normalization."""
    norm_map = defaultdict(list)
    for intent in intents:
        norm_map[normalize_intent(intent)].append(intent)

    survivors = []
    merged_count = 0
    for norm, group in norm_map.items():
        rep = max(group, key=len)  # keep longest (most descriptive)
        survivors.append(rep)
        if len(group) > 1:
            merged_count += len(group) - 1
            log.info(f"  [Norm] Merged {len(group)} → 1: \"{rep}\"")

    return survivors, merged_count


def generate_intent_embeddings(bedrock_client, intents, cache_file):
    """Generate or load cached embeddings for intents."""
    cached = {}
    if os.path.exists(cache_file):
        try:
            cached = json.load(open(cache_file))
            log.info(f"  Loaded {len(cached)} cached embeddings")
        except:
            pass

    embeddings = {}
    to_embed = []

    for intent in intents:
        norm = normalize_intent(intent)
        if norm in cached and cached[norm] is not None:
            embeddings[intent] = cached[norm]
        else:
            to_embed.append(intent)

    if to_embed:
        log.info(f"  Generating {len(to_embed)} new embeddings ({len(embeddings)} cached)...")
        for i, intent in enumerate(to_embed):
            if i > 0 and i % 50 == 0:
                print(f"    Embedded {i}/{len(to_embed)}...", flush=True)
            try:
                norm = normalize_intent(intent)
                response = bedrock_client.invoke_model(
                    modelId=EMBEDDING_MODEL,
                    body=json.dumps({"inputText": norm}),
                    contentType="application/json",
                    accept="application/json"
                )
                result = json.loads(response["body"].read())
                embeddings[intent] = result["embedding"]
                cached[norm] = result["embedding"]
                time.sleep(0.05)
            except Exception as e:
                log.warning(f"  Embedding failed for '{intent[:50]}': {e}")

        with open(cache_file, "w") as f:
            json.dump(cached, f)

    return embeddings


def dbscan_cluster_intents(intents, embeddings, eps=DEFAULT_DBSCAN_EPS):
    """Cluster intents using DBSCAN on cosine distance. Returns {label: [intents]}."""
    valid = [(i, intent) for i, intent in enumerate(intents) if intent in embeddings]
    if not valid:
        return {-1: intents}

    indices, valid_intents = zip(*valid)
    emb_matrix = np.array([embeddings[intent] for intent in valid_intents])
    dist_matrix = cosine_distances(emb_matrix)

    labels = DBSCAN(eps=eps, min_samples=2, metric="precomputed").fit_predict(dist_matrix)

    clusters = defaultdict(list)
    for i, label in enumerate(labels):
        clusters[label].append(valid_intents[i])

    # Add intents without embeddings to noise
    valid_set = set(valid_intents)
    for intent in intents:
        if intent not in valid_set:
            clusters[-1].append(intent)

    return dict(clusters)


_auto_approve = False

def _is_interactive():
    """Check if stdin is a TTY (interactive terminal)."""
    try:
        return os.isatty(sys.stdin.fileno())
    except Exception:
        return False

def ask_user(prompt_text):
    """Interactive feedback. Auto-approves if --auto-approve flag is set or stdin is not a TTY."""
    if _auto_approve or not _is_interactive():
        print(f"\n{prompt_text}")
        print("  [AUTO-APPROVED]")
        return "approve", None
    print(f"\n{prompt_text}")
    print("[A]pprove / [E]dit / [S]kip / [Q]uit")
    while True:
        try:
            choice = input("> ").strip().lower()
        except EOFError:
            print("  [AUTO-APPROVED — no interactive input available]")
            return "approve", None
        if choice in ("a", "approve"): return "approve", None
        if choice in ("s", "skip"): return "skip", None
        if choice in ("q", "quit"): return "quit", None
        if choice in ("e", "edit"):
            try:
                feedback = input("Enter corrections: > ").strip()
            except EOFError:
                return "approve", None
            return "edit", feedback
        print("Invalid. Enter A/E/S/Q")


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

INTENT_SYSTEM = """You are a Functional Intent Extraction Agent. Extract HIGH-LEVEL FUNCTIONAL INTENTS from the given input.

A functional intent is a descriptive business capability phrase — what a user or system
can DO, with enough context to understand the purpose.

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

**Do NOT invent roles from domain vocabulary:**
- Do NOT assign "Admin" or "Moderator" unless the code explicitly checks
  user roles or permissions (e.g., role-based middleware, admin guards,
  isAdmin checks, permission decorators).
- A backend service that processes moderation requests is "System", not "Moderator".
- A service that uploads/validates content is "System", not "Admin".
- If no role-based access control exists in the code, use "User" (for
  user-triggered) or "System" (for automated).

**Forbidden persona names — NEVER use:**
Developer, Engineer, Programmer, Architect, API, Service, Component,
Module, Worker, Backend, Frontend, Database, Controller, Handler, Repository

## INTENT RULES
1. Extract ONE intent per DISTINCT business capability found in the code.
   - Do NOT split one capability into multiple intents
   - Do NOT merge unrelated capabilities into one intent
   - There is NO upper limit — extract as many as the code warrants
   - A single file with 10 distinct functions may produce 5-10 intents
   - A cluster with 20 files may produce 10-20 intents
   - If only one capability exists, return just 1
2. Each intent = "Persona: Descriptive capability phrase" (5-15 words, starts with verb)
   Intent MUST include context — what is being done, for what purpose, to/from where.
   BAD:  "Transform Data" (too vague — transform what? for what purpose?)
   GOOD: "Transform order data for invoice generation with tax calculation"
   BAD:  "Process Events" (too vague — which events? what processing?)
   GOOD: "Process payment events to update account balances and ledger entries"
   BAD:  "Manage Profile" (too vague — which profile? what management?)
   GOOD: "Update user billing profile with payment methods and addresses"
   BAD:  "Send Notifications" (too vague — what kind? triggered by what?)
   GOOD: "Send email notifications to customers when order status changes"
3. If multiple functions/methods contribute to the SAME business capability,
   merge into ONE intent.
4. For code input: ask "What does this code enable a user or operator to do?"
5. For backend code with route decorators (@Get, @Post, etc.):
   derive the business capability from the route purpose, not the path.
6. For pure backend code (jobs, workers, event handlers with no UI trigger):
   use "System" as persona.
7. If input contains ONLY data models, schemas, configs, type definitions,
   or internal utilities with no user-facing behavior → return []
   Non-functional code to SKIP (never generate intents for):
   - UI rendering internals: loading skeletons, spinners, error boundaries,
     tooltip positioning, CSS/theme utilities, font metric parsing
   - Component plumbing: state management wrappers, context providers,
     event handler registrations, debounce/throttle utilities
   - Build/deploy: webpack configs, Docker, nginx, CI/CD pipelines,
     environment variable loading, health check endpoints
   - Generic CRUD helpers: base service classes, abstract repositories,
     generic pagination/filter utilities (capture the SPECIFIC entity
     CRUD that uses them, not the utility itself)

8. When a single function or API endpoint handles MULTIPLE DISTINCT BUSINESS WORKFLOWS
   distinguished by flags, parameters, type arguments, or conditional branches, extract
   SEPARATE intents for each workflow variant. Do NOT merge them into one generic intent.
   Examples of flag-based workflow splitting:
   - A function that creates both inbound and outbound records based on a direction flag
     → TWO intents: one for inbound, one for outbound
   - A function that handles both creating and cancelling records based on an action parameter
     → TWO intents: one for create, one for cancel
   - An API that serves different entity types based on a type query parameter
     → SEPARATE intents per entity type
   - A form component that renders differently based on a mode prop (create vs edit vs view)
     → ONE intent (same entity, CRUD is one capability)

9. When extracting intents from BACKEND API code, look for these patterns that indicate
   DISTINCT user workflows (extract separate intents for each):
   - Different HTTP methods on the same route (GET vs POST vs PUT vs DELETE)
   - Request parameter switches (e.g., ?type=sale vs ?type=purchase)
   - Flag-based branching in handler logic (e.g., if flag == 9 vs flag == 3)
   - Separate list/detail/create/cancel endpoints for the same entity
   - Different view_config decorators on the same class

10. When extracting intents from FRONTEND code, look for these patterns:
    - Route definitions with type/mode query parameters (e.g., /invoice?type=sale)
    - Workflow configuration objects that define different tabs or sections
    - Components that render different forms based on props
    - Navigation menu items that map to distinct business workflows
    Each distinct navigation path or workflow tab = a separate intent.

11. When the input includes BRANCH, ROUTE, or DB annotations on methods, these reveal
    the INTERNAL WORKFLOW VARIANTS within that method. Each distinct branch path that
    serves a different business purpose = a separate intent.
    - BRANCH annotations show conditional logic (flags, types, modes)
    - ROUTE annotations show HTTP method or parameter-based routing
    - DB annotations show which data entities are affected
    Use these to identify workflow variants that would otherwise be hidden inside
    a single method signature.

Return ONLY a JSON array: ["Persona: Descriptive intent phrase", ...]
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

## OUTCOME DISTRIBUTION RULES

- NEVER create a single catch-all Outcome for a persona (e.g., "Process Backend
  Operations" or "Handle All System Tasks"). This makes downstream scenario
  generation fail because file discovery cannot target a vague outcome.
- If a persona has 10+ intents mapped to it, it MUST have at least 3 outcomes.
- If a persona has 20+ intents, it MUST have at least 5 outcomes.
- System persona outcomes should be grouped by domain concern, not lumped together.
- Each outcome should contain AT MOST 6 intents. If an outcome accumulates more than 6,
  it is too broad and MUST be split into more specific outcomes.
  Example of a too-broad outcome:
    "Transaction Management" with 9 intents covering vouchers, invoices, bank reconciliation,
    and bill adjustments → split into "Voucher Management", "Invoice Management",
    "Bank Reconciliation"
- When splitting, group by the primary ENTITY being managed (the noun), not by the
  action (the verb). "Create Order" and "Cancel Order" belong together under
  "Order Management", but "Create Order" and "Create Invoice" do NOT.

**Good System outcomes (domain-focused):**
- "Process Event Queues"
- "Manage Search and Embeddings"
- "Process Content Moderation"
- "Handle Email Notifications"
- "Process Resume and Skills"

**Bad System outcomes (catch-all anti-patterns):**
- "Process Backend Operations" (too broad — covers everything)
- "Handle System Tasks" (meaningless grouping)
- "Manage Infrastructure" (implementation, not capability)

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

OUTCOME_ASSIGN_SYSTEM = """You are an Outcome Assignment Agent.

Given a cluster of RELATED functional intents for a single persona, do FOUR things:

1. FILTER NON-FUNCTIONAL: Drop intents that describe infrastructure, not business capabilities.
   These are NOT functional intents — drop them immediately:
   - Validation schemas, DTO definitions, type definitions (e.g., "Define validation schemas for X")
   - Database index creation, vector index setup, text search configuration
   - Database connection management, session handling, transaction plumbing
   - JSON serialization/deserialization, circular reference handling, object graph reconstruction
   - HTTP client wrappers, generic API request helpers
   - Route/controller decorator definitions, authentication guards/middleware
   - Error boundaries, lazy loading, retry mechanisms
   - Theme switching, dark mode toggling
   - Pagination mechanics, sidebar/panel layout, dropdown mechanics
   - Unsaved changes detection, loading states, progress indicators
   - Auth token refresh, session sync across tabs
   - Font parsing, glyph metrics, typography internals
   - Geometric calculations, point interpolations (unless the product IS a geometry tool)

   HOWEVER: If a non-functional intent contains SOME business logic, ABSORB it into the
   related business intent rather than dropping it entirely.
   Example: "Define validation schemas for user story management" → absorb into
   "Create and manage user stories" (the validation supports the business capability)

2. MERGE SIMILAR: If multiple intents describe overlapping aspects of the SAME capability,
   merge them into ONE intent with a richer, more descriptive phrase that captures the
   combined meaning. The merged intent should be 5-15 words and cover all merged inputs.
   Example:
     Input:  ["Create functional nodes with metadata", "Update functional graph node properties"]
     Merged: "Create and update functional graph nodes with detailed metadata and properties"

3. DEDUPLICATE: After merging, if any remaining intents are exact or near-exact duplicates,
   drop the less descriptive one.

4. ASSIGN OUTCOMES: Map each final intent (merged or kept as-is) to an Outcome.

MERGE RULES:
- Merge intents that describe the SAME business entity with different operations or details
- The merged intent MUST preserve all distinct information from the inputs
- Do NOT merge intents with different VERBS that represent different capabilities:
  Create vs Clone, Update vs Delete, Search vs Filter, Import vs Export
  "Create X" and "Clone X" are NOT the same — creating from scratch ≠ copying existing
- Do NOT merge intents about different entities or different data sources

DEDUP RULES (applied AFTER merging):
- Near-identical wording after merge: DROP the less descriptive one
- Singular vs plural: DROP one
- Generic + specific version of same action: KEEP specific, DROP generic
- Different filter/criteria (by Skills vs by City): KEEP BOTH (different capabilities)
- Action vs viewing result (Follow vs Get Followed): KEEP BOTH (different flows)
- Same operation on different data sources: KEEP BOTH (different pipelines)
- When in doubt, KEEP BOTH. False negatives (missing intents) are worse than false positives (extra intents)

OUTCOME RULES:
- Outcomes = high-level business capabilities (not technical functions)
- REUSE existing outcomes when provided
- Only create new outcomes if no existing one fits
- Target 3-8 outcomes per persona total

OUTCOME SIZE RULES:
- There is NO hard cap on intents per outcome. A complex entity may have
  10-15 intents covering create, edit, delete, search, export, import, etc.
  — these all belong under ONE outcome if they share the same primary entity.
- Only split an outcome when intents cover DIFFERENT ENTITIES or clearly
  different domain areas, not different operations on the same entity.
- Group by PRIMARY ENTITY, not by operation. All intents related to the
  same entity belong under ONE outcome like "Manage [Entity]", NOT split
  into separate outcomes per operation.
- If existing outcomes list contains two outcomes for the same entity
  under different operation names, consolidate into the more specific
  one and reassign intents.

OUTPUT FORMAT (strict JSON):
{
  "unique_intents": [
    {"intent": "<final intent text>", "outcome": "<outcome name>", "merged_from": ["<original 1>", "<original 2>"]}
  ],
  "dropped_intents": [
    {"intent": "<dropped>", "reason": "<why dropped — non-functional | duplicate | absorbed into X>", "kept_as": "<the representative, or null if pure infrastructure>"}
  ]
}

NOTE: "merged_from" is optional — include it only when the intent was merged from multiple inputs.
If the intent was kept as-is, omit "merged_from".
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
- Intents are the PRIMARY driver for scenarios, not individual functions.
  Each intent should map to roughly 1 scenario. Only create additional
  scenarios if the code reveals a genuinely distinct user flow that no
  intent covers.
- Do NOT create a separate scenario for each function/method. Multiple
  functions that contribute to the same user flow (e.g., save, validate,
  serialize, upload) should be ONE scenario with multiple steps.

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

### API LINKING on actions
- If the code shows an action triggers a REST API call (route decorator,
  fetch/axios call, apiFetch, HTTP method), attach an "apis" array to that action.
- Extract: type (REST | GraphQL | gRPC | WebSocket | Event), method, url, request shape, response shape
- type = the protocol. method = the operation verb for that protocol.
- For REST: type="REST", method=GET|POST|PUT|DELETE|PATCH, url="/path"
- For GraphQL: type="GraphQL", method=QUERY|MUTATION|SUBSCRIPTION, url=operation name
- For gRPC: type="gRPC", method=UNARY|SERVER_STREAM|CLIENT_STREAM|BIDI_STREAM, url=Service.Method
- For WebSocket: type="WebSocket", method=EMIT|ON|SUBSCRIBE, url=event name
- For Event: type="Event", method=PUBLISH|CONSUME, url=topic/event name
- Derive from route decorators (@Get, @Post, @Put, @Delete) or fetch URLs in code
- Default type to "REST" if not explicitly another protocol
- Not every action has an API — only add when the code evidence is clear
- If no API call is involved, omit the "apis" field entirely (do not add empty array)

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
[{"scenario": "<title>", "steps": [{"step": "<purpose>", "actions": [{"action": "<interaction>", "description": "<detail or null>", "apis": [{"type": "REST", "method": "<GET|POST|PUT|DELETE|PATCH>", "url": "<path>", "request": "<payload shape>", "response": "<response shape>"}]}]}]}]

NOTE: "apis" is optional — include ONLY when the action triggers an API call visible in the code. Omit for actions with no API involvement. Default type to "REST" unless code shows GraphQL/gRPC/WebSocket/Event.
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
    parser.add_argument("--skip-single-file-clusters", action="store_true", help="Skip clusters with only 1 file (old behavior)")
    parser.add_argument("--batch-clusters", type=int, default=0, metavar="MAX_FILES",
                        help="Batch small clusters together (max files per batch). Default 0 = process each cluster separately.")
    parser.add_argument("--eps", type=float, default=DEFAULT_DBSCAN_EPS,
                        help=f"DBSCAN eps (cosine distance). 0.15=strict, 0.20=moderate, 0.30=loose. Default: {DEFAULT_DBSCAN_EPS}")
    parser.add_argument("--resume", action="store_true", help="Resume from cached pass results (skip completed passes)")
    parser.add_argument("--resume-from", type=int, choices=[1, 2, 3], help="Resume from a specific pass number (1, 2, or 3)")
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

    # Determine resume point
    resume_from = 1  # default: start fresh
    if args.resume_from:
        resume_from = args.resume_from
        print(f"\n  [Cache] Resuming from Pass {resume_from} (as requested)")
    elif args.resume:
        # Auto-detect: find the latest completed pass
        if load_pass_cache(2):
            resume_from = 3
            print(f"\n  [Cache] Found Pass 2 cache — resuming from Pass 3")
        elif load_pass_cache(1):
            resume_from = 2
            print(f"\n  [Cache] Found Pass 1 cache — resuming from Pass 2")
        else:
            print(f"\n  [Cache] No cache found — starting fresh")

    # ======================================================================
    # PASS 1: Extract intents from all clusters
    # ======================================================================
    print(f"\n{'='*60}")
    print("PASS 1: Extracting intents from all clusters")
    print(f"{'='*60}\n")

    all_intents = {}  # cluster_id → [intents]
    flat_intents = []  # all intents flattened

    if resume_from > 1:
        cached = load_pass_cache(1)
        if cached:
            all_intents = cached.get("all_intents", {})
            flat_intents = cached.get("flat_intents", [])
            print(f"  [Cache] Skipping Pass 1 — loaded {len(flat_intents)} intents from {len(all_intents)} clusters")
        else:
            print("  [Cache] ERROR: No Pass 1 cache found, cannot skip. Starting fresh.")
            resume_from = 1

    if resume_from <= 1:
        ontologies = api.get_ontologies(project_uuid)
        all_clusters = []
        for ont in ontologies:
            oid = ont.get("_id") or ont.get("id")
            clusters = api.get_clusters(project_uuid, str(oid))
            for c in clusters:
                c["_ontName"] = ont.get("name", "?")
            all_clusters.extend(clusters)

        # Optionally filter clusters
        clusters_to_process = list(all_clusters)
        if args.skip_single_file_clusters:
            clusters_to_process = [c for c in clusters_to_process if int(c.get("fileCount", 0)) >= 2]
            print(f"  --skip-single-file-clusters: skipped {len(all_clusters) - len(clusters_to_process)} single-file clusters")
        if args.cluster:
            clusters_to_process = [c for c in clusters_to_process if c.get("clusterId") == args.cluster]

        print(f"Total clusters: {len(all_clusters)}, processing: {len(clusters_to_process)}")

        MAX_BATCH_FILES = args.batch_clusters  # 0 = process each cluster separately

        if MAX_BATCH_FILES > 0:
            # Batched mode: group small clusters together (legacy behavior)
            print(f"  Cluster batching ENABLED (max {MAX_BATCH_FILES} files per batch)")
            batches = []
            current_batch = {"cluster_ids": [], "files": []}

            for ci, cluster in enumerate(clusters_to_process):
                cid = cluster.get("clusterId")
                fc = int(cluster.get("fileCount", 0))
                print(f"  Fetching cluster {ci+1}/{len(clusters_to_process)} (id={cid}, ~{fc} files)...", flush=True)
                files = api.get_cluster_files(project_uuid, cid)
                if not files:
                    print(f"  Cluster {cid}: empty, skipping", flush=True)
                    continue

                if fc >= MAX_BATCH_FILES:
                    if current_batch["files"]:
                        batches.append(current_batch)
                        current_batch = {"cluster_ids": [], "files": []}
                    batches.append({"cluster_ids": [cid], "files": files})
                else:
                    if len(current_batch["files"]) + len(files) > MAX_BATCH_FILES and current_batch["files"]:
                        batches.append(current_batch)
                        current_batch = {"cluster_ids": [], "files": []}
                    current_batch["cluster_ids"].append(cid)
                    current_batch["files"].extend(files)

            if current_batch["files"]:
                batches.append(current_batch)

            print(f"  Aggregated into {len(batches)} batches")

            for i, batch in enumerate(batches):
                cids = batch["cluster_ids"]
                files = batch["files"]
                cid_label = ", ".join(str(c) for c in cids)
                print(f"  [{i+1}/{len(batches)}] Batch (clusters: {cid_label}, {len(files)} files)...", end=" ", flush=True)

                try:
                    summary = format_summary(files)
                    chunks = chunk_text(summary, max_chars=80000)
                    if len(chunks) > 1:
                        print(f"{len(files)} files → {len(chunks)} chunks")

                    batch_intents = []
                    for chi, chunk in enumerate(chunks):
                        if len(chunks) > 1:
                            print(f"    Chunk {chi+1}/{len(chunks)} ({len(chunk)} chars)...", end=" ")
                        chunk_intents = None
                        for retry in range(3):
                            try:
                                chunk_intents = llm.call_json(INTENT_SYSTEM, f"Extract intents:\n\n{chunk}")
                                if chunk_intents:
                                    break
                            except Exception as retry_e:
                                if retry < 2:
                                    print(f"retry {retry+1}/2 ({retry_e})...", end=" ")
                                    time.sleep(3)
                                else:
                                    print(f"failed after 3 attempts: {retry_e}")
                        if chunk_intents:
                            batch_intents.extend(chunk_intents)
                            if len(chunks) > 1:
                                print(f"{len(chunk_intents)} intents")
                        elif len(chunks) > 1:
                            print("no-op")

                    batch_intents = list(set(batch_intents))
                    if batch_intents:
                        for cid in cids:
                            all_intents[cid] = batch_intents
                        flat_intents.extend(batch_intents)
                        print(f"{len(batch_intents)} intents")
                    else:
                        print("no-op")
                except Exception as e:
                    print(f"error: {e}")

            print(f"\nTotal: {len(flat_intents)} intents from {len(batches)} batches ({len(all_intents)} clusters)")

        else:
            # Default: process each cluster individually (no cross-cluster intent duplication)
            # Large clusters (>20 files) are split into file batches
            MAX_FILES_PER_CALL = 20  # v4: reduced from 30 to accommodate method-level detail
            print(f"  Cluster batching DISABLED (each cluster processed separately, max {MAX_FILES_PER_CALL} files per LLM call)")

            for ci, cluster in enumerate(clusters_to_process):
                cid = cluster.get("clusterId")
                fc = int(cluster.get("fileCount", 0))
                print(f"  [{ci+1}/{len(clusters_to_process)}] Cluster {cid} (~{fc} files)...", end=" ", flush=True)
                files = api.get_cluster_files(project_uuid, cid)
                if not files:
                    print(f"empty, skipping", flush=True)
                    continue

                try:
                    # Split files into batches if cluster is large
                    file_batches = [files[j:j+MAX_FILES_PER_CALL]
                                    for j in range(0, len(files), MAX_FILES_PER_CALL)]

                    if len(file_batches) > 1:
                        print(f"{len(files)} files → {len(file_batches)} file batches")

                    cluster_intents = []
                    for fbi, file_batch in enumerate(file_batches):
                        if len(file_batches) > 1:
                            print(f"    File batch {fbi+1}/{len(file_batches)} ({len(file_batch)} files)...", end=" ", flush=True)

                        summary = format_summary(file_batch)
                        chunks = chunk_text(summary, max_chars=80000)

                        for chi, chunk in enumerate(chunks):
                            if len(chunks) > 1:
                                print(f"chunk {chi+1}/{len(chunks)}...", end=" ")
                            batch_intents = None
                            for retry in range(3):
                                try:
                                    batch_intents = llm.call_json(INTENT_SYSTEM, f"Extract intents:\n\n{chunk}")
                                    if batch_intents:
                                        break
                                except Exception as retry_e:
                                    if retry < 2:
                                        print(f"retry {retry+1}/2 ({retry_e})...", end=" ")
                                        time.sleep(3)
                                    else:
                                        print(f"failed after 3 attempts: {retry_e}")
                            if batch_intents:
                                cluster_intents.extend(batch_intents)
                                if len(file_batches) > 1 or len(chunks) > 1:
                                    print(f"{len(batch_intents)} intents", end=" ")

                        if len(file_batches) > 1:
                            print()

                    cluster_intents = list(set(cluster_intents))
                    if cluster_intents:
                        all_intents[cid] = cluster_intents
                        flat_intents.extend(cluster_intents)
                        print(f"{len(cluster_intents)} intents")
                    else:
                        print("no-op")
                except Exception as e:
                    print(f"error: {e}")

            print(f"\nTotal: {len(flat_intents)} intents from {len(clusters_to_process)} clusters ({len(all_intents)} with intents)")

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
            print(f"\nRequires Node.js exactly v22.x (Node 24+ fails silently due to tree-sitter ESM/TLA). Once uploaded, re-run this script.")
            return

        # Cache Pass 1 results
        save_pass_cache(1, {"all_intents": all_intents, "flat_intents": flat_intents})

    # ======================================================================
    # PASS 1.5: Intent dedup (filter + normalize + embed + DBSCAN)
    # ======================================================================
    persona_clusters = None

    # Check if Pass 1.5 results are cached
    embeddings = {}  # Initialize — will be populated from cache or generated fresh
    cached_1_5 = load_pass_cache("1.5")
    if cached_1_5 and resume_from >= 2:
        persona_clusters = {}
        for persona, clusters_dict in cached_1_5.get("persona_clusters", {}).items():
            persona_clusters[persona] = {int(k) if k.lstrip('-').isdigit() else k: v
                                          for k, v in clusters_dict.items()}
        total_cached = sum(len(v) for c in persona_clusters.values() for v in c.values())
        print(f"\n  [Cache] Loaded Pass 1.5 — {len(persona_clusters)} personas, {total_cached} intents. Skipping dedup pipeline.")

        # Load embeddings from cache (needed for singleton similarity sorting in Pass 2)
        embedding_cache = os.path.join(os.getcwd(), "llm_logs_v4", "intent_embeddings_v4.json")
        if os.path.exists(embedding_cache):
            try:
                emb_raw = json.load(open(embedding_cache))
                all_intents_flat = [i for clusters in persona_clusters.values() for v in clusters.values() for i in v]
                for intent in all_intents_flat:
                    norm = normalize_intent(intent)
                    if norm in emb_raw and emb_raw[norm] is not None:
                        embeddings[intent] = emb_raw[norm]
                print(f"  [Cache] Loaded {len(embeddings)} embeddings for singleton sorting")
            except Exception as e:
                log.warning(f"  Could not load embeddings cache: {e}")
    else:
        print(f"\n{'='*60}")
        print("PASS 1.5: Intent deduplication pipeline")
        print(f"{'='*60}\n")

    if persona_clusters is None:
        FILTER_KEYWORDS = [
            # Test/mock/benchmark
            "Test ", "Mock ", "Benchmark",
            # Server startup and initialization
            "Initialize ", "Establish ", "Run Service Initialization",
            "Register API Handlers",
            "Start Application", "Start Web Server",
            "Start Moderation Service",
            # Database/connection setup
            "Database Migration", "Database Connection", "Connect to ",
            # Build tooling and dev environment
            "Vite", "Frontend Build", "Development Environment",
            "Configure Frontend Environment",
            # Infrastructure configuration
            "Configure GRPC", "Configure gRPC",
            "Configure Application Router",
            "Configure Server Router", "Configure Service Router",
            "Configure Logging",
            # UI rendering internals (specific patterns only)
            "Render Loading", "Render Skeleton", "Render Fallback",
            "Render Tooltip", "Render Error Boundary", "Render Spinner",
            "Re-render Component",
            "Font Rendering", "Font Metric", "Font Loading",
            "Parse SVG Path", "Transform SVG Coordinates",
            "Skeleton Loading", "Loading Spinner", "Loading Fallback",
            "Error Boundary",
            # Generic component plumbing
            "State Management", "Context Provider",
            "Event Handler", "Event Listener",
            "Debounce ", "Throttle ",
            # Build/deploy/infra
            "Webpack", "Docker", "Nginx",
            "CI/CD", "Pipeline Configuration",
            "Environment Variable",
            "Health Check Endpoint",
            "CORS Configuration",
        ]

        def _is_non_functional(intent):
            text = intent.split(": ", 1)[-1] if ": " in intent else intent
            return any(kw in text for kw in FILTER_KEYWORDS)

        pre_filter_count = len(flat_intents)
        flat_intents = [i for i in flat_intents if not _is_non_functional(i)]
        print(f"  Step 1 - Keyword filter: {pre_filter_count} → {len(flat_intents)} (-{pre_filter_count - len(flat_intents)})")

        # Step 2: Exact dedup
        unique_intents = sorted(set(flat_intents))
        print(f"  Step 2 - Exact dedup: {len(flat_intents)} → {len(unique_intents)} (-{len(flat_intents) - len(unique_intents)})")

        # Step 3: Normalization dedup
        unique_intents, norm_merged = normalization_dedup(unique_intents)
        print(f"  Step 3 - Normalization dedup: → {len(unique_intents)} (-{norm_merged})")

        # Step 4: Group by persona
        persona_intents = defaultdict(list)
        for intent in unique_intents:
            persona = intent.split(": ", 1)[0] if ": " in intent else "User"
            persona_intents[persona].append(intent)

        for pname, intents in sorted(persona_intents.items()):
            print(f"    {pname}: {len(intents)} intents")

        # Step 5: Embeddings + DBSCAN clustering per persona
        dbscan_eps = args.eps
        sim_threshold = 1 - dbscan_eps
        print(f"\n  Step 5 - Embedding + DBSCAN clustering (eps={dbscan_eps}, similarity >= {sim_threshold:.2f})...")
        embedding_cache = os.path.join(os.getcwd(), "llm_logs_v4", "intent_embeddings_v4.json")
        all_flat = [i for intents in persona_intents.values() for i in intents]
        embeddings = generate_intent_embeddings(llm.client, all_flat, embedding_cache)

        persona_clusters = {}
        for persona, intents in sorted(persona_intents.items()):
            clusters = dbscan_cluster_intents(intents, embeddings, eps=dbscan_eps)
            persona_clusters[persona] = clusters
            named = sum(1 for k in clusters if k != -1)
            noise = len(clusters.get(-1, []))
            print(f"    {persona}: {len(intents)} intents → {named} clusters + {noise} singletons")

    # ---- Display clustering results for review ----
    print(f"\n{'='*60}")
    print("CLUSTERING RESULTS")
    print(f"{'='*60}")
    print("""
  Intents were grouped by semantic similarity using embeddings + DBSCAN.
  Intents within the same cluster describe similar capabilities and will
  be sent together to Sonnet for deduplication and outcome assignment.

  Singletons are intents with no close semantic match — they will be
  processed separately and assigned to outcomes individually.

  Review the clusters below to verify:
    - Related intents are grouped together (good clustering)
    - Unrelated intents are NOT in the same cluster (no false grouping)
    - Important intents are not missing (nothing filtered incorrectly)
""")

    for persona, clusters in sorted(persona_clusters.items()):
        named_clusters = [(cid, members) for cid, members in clusters.items() if cid != -1]
        noise = clusters.get(-1, [])
        total = sum(len(v) for v in clusters.values())
        print(f"  {persona} ({total} intents: {len(named_clusters)} clusters + {len(noise)} singletons)")
        print(f"  {'-'*56}")

        for cid, members in sorted(named_clusters, key=lambda x: -len(x[1])):
            print(f"\n    Cluster {cid} ({len(members)} intents — will be sent together to Sonnet):")
            for m in sorted(members):
                print(f"      - {m.split(': ', 1)[-1]}")

        if noise:
            print(f"\n    Singletons ({len(noise)} — will be batched separately):")
            for m in sorted(noise):
                print(f"      - {m.split(': ', 1)[-1]}")

    action, _ = ask_user("\nReview clustering above. [A]pprove to proceed to outcome assignment, [S]kip to abort:")
    if action in ("skip", "quit"):
        print("Aborting.")
        return

    # Cache Pass 1.5 results (dedup + clustering)
    save_pass_cache("1.5", {
        "persona_clusters": {
            persona: {str(k): v for k, v in clusters.items()}
            for persona, clusters in persona_clusters.items()
        }
    })

    # ======================================================================
    # PASS 2: Create outcomes via cluster-based assignment (Sonnet)
    # ======================================================================
    print(f"\n{'='*60}")
    print("PASS 2: Cluster-based outcome assignment (Sonnet dedup + assign)")
    print(f"{'='*60}\n")

    structure = None

    if resume_from > 2:
        cached = load_pass_cache(2)
        if cached:
            structure = cached.get("structure")
            print(f"  [Cache] Skipping Pass 2 — loaded {len(structure)} personas from cache")
        else:
            print("  [Cache] ERROR: No Pass 2 cache found, cannot skip. Running Pass 2.")
            resume_from = 2

    if resume_from <= 2:
        # Check if functional graph is empty
        try:
            existing_personas = api.get_personas(project_uuid)
        except Exception as e:
            log.warning(f"  Could not check existing personas: {e}. Proceeding anyway.")
            existing_personas = []
        if existing_personas:
            persona_names = [p.get('persona') for p in existing_personas]
            print(f"\n  WARNING: Graph already has {len(existing_personas)} personas: {persona_names}")
            action, _ = ask_user("Graph is not empty. [A]pprove to continue (will merge), [S]kip to abort:")
            if action in ("skip", "quit"):
                print("Aborting. Delete existing graph data or use a new project.")
                return

        structure = []
        total_dropped = 0

        for persona, clusters in sorted(persona_clusters.items()):
            print(f"\n  --- {persona} ---")
            existing_outcomes = []
            persona_outcome_intents = {}  # outcome → [intents]

            # Process named clusters — batch small clusters together, large ones alone
            CLUSTER_BATCH_TARGET = 25  # target intents per Sonnet call
            sorted_clusters = sorted(
                [(cid, members) for cid, members in clusters.items() if cid != -1],
                key=lambda x: -len(x[1])
            )
            noise = clusters.get(-1, [])

            # Split into large clusters (process alone) and small clusters (batch together)
            large_clusters = [(cid, m) for cid, m in sorted_clusters if len(m) >= CLUSTER_BATCH_TARGET // 2]
            small_clusters = [(cid, m) for cid, m in sorted_clusters if len(m) < CLUSTER_BATCH_TARGET // 2]

            MAX_INTENTS_PER_OUTCOME_IN_CONTEXT = 5  # show last N intents per outcome in prompt

            def _build_existing_context():
                """Build existing outcomes with recent intents for Sonnet context."""
                if not persona_outcome_intents:
                    return "[]"
                context = {}
                for outcome, intents in persona_outcome_intents.items():
                    # Strip persona prefix, show last N
                    stripped = [i.split(": ", 1)[-1] for i in intents]
                    if len(stripped) <= MAX_INTENTS_PER_OUTCOME_IN_CONTEXT:
                        recent = stripped
                    else:
                        # First 3 (define scope) + last 2 (most recent, likely to overlap)
                        recent = stripped[:3] + ["..."] + stripped[-2:]
                    extra = max(0, len(intents) - MAX_INTENTS_PER_OUTCOME_IN_CONTEXT)
                    if extra > 0:
                        recent.append(f"... +{extra} more")
                    context[outcome] = recent
                return json.dumps(context, indent=2)

            # Batch small clusters into groups up to CLUSTER_BATCH_TARGET
            cluster_batches = []  # each: [{"cid": id, "members": [...]}]
            current_batch = []
            current_size = 0
            for cid, members in small_clusters:
                if current_size + len(members) > CLUSTER_BATCH_TARGET and current_batch:
                    cluster_batches.append(current_batch)
                    current_batch = []
                    current_size = 0
                current_batch.append({"cid": cid, "members": members})
                current_size += len(members)
            if current_batch:
                cluster_batches.append(current_batch)

            # Process large clusters — chunk if exceeds CLUSTER_BATCH_TARGET
            MAX_PER_CALL = CLUSTER_BATCH_TARGET  # max intents per Sonnet call

            for cid, members in large_clusters:
                chunks = [members[i:i+MAX_PER_CALL] for i in range(0, len(members), MAX_PER_CALL)]

                for chi, chunk in enumerate(chunks):
                    existing_str = _build_existing_context()
                    stripped = [m.split(": ", 1)[-1] for m in chunk]

                    chunk_label = f" part {chi+1}/{len(chunks)}" if len(chunks) > 1 else ""
                    prompt = f"""Persona: {persona}

Existing outcomes with their assigned intents (REUSE outcomes, drop intents that duplicate already-assigned ones):
{existing_str}

Cluster of related intents to process:
{json.dumps(stripped, indent=2)}

IMPORTANT:
1. First identify and DROP duplicate intents (same capability, different wording)
2. Then assign each UNIQUE remaining intent to an outcome
3. Reuse existing outcomes when possible"""

                    print(f"    Cluster {cid}{chunk_label} ({len(chunk)} intents)...", end=" ", flush=True)
                    result = llm.call_json(OUTCOME_ASSIGN_SYSTEM, prompt,
                                           max_tokens=8192, model=sonnet_model)

                    if result and isinstance(result, dict):
                        for item in result.get("unique_intents", []):
                            outcome = item.get("outcome", "Uncategorized")
                            intent = f"{persona}: {item['intent']}"
                            persona_outcome_intents.setdefault(outcome, []).append(intent)
                            if outcome not in existing_outcomes:
                                existing_outcomes.append(outcome)
                        dropped = result.get("dropped_intents", [])
                        total_dropped += len(dropped)
                        kept = len(result.get("unique_intents", []))
                        print(f"→ {kept} kept, {len(dropped)} dropped, {len(existing_outcomes)} outcomes")
                    else:
                        for m in chunk:
                            persona_outcome_intents.setdefault("Uncategorized", []).append(m)
                        print(f"→ fallback, kept all {len(chunk)}")
                    time.sleep(3)

            # Process batched small clusters
            for bi, batch in enumerate(cluster_batches):
                batch_cids = [c["cid"] for c in batch]
                all_members = []
                for c in batch:
                    all_members.extend(c["members"])

                existing_str = _build_existing_context()

                # Format with cluster labels so Sonnet knows which intents are related
                cluster_sections = []
                for c in batch:
                    stripped = [m.split(": ", 1)[-1] for m in c["members"]]
                    cluster_sections.append(f"  Related group (cluster {c['cid']}): {json.dumps(stripped)}")
                clusters_text = "\n".join(cluster_sections)

                prompt = f"""Persona: {persona}

Existing outcomes with their assigned intents (REUSE outcomes, drop intents that duplicate already-assigned ones):
{existing_str}

Multiple clusters of related intents to process:
{clusters_text}

IMPORTANT:
1. First identify and DROP duplicate intents — both within and across clusters
2. Then assign each UNIQUE remaining intent to an outcome
3. Reuse existing outcomes when possible"""

                cid_label = ", ".join(str(c) for c in batch_cids)
                print(f"    Clusters [{cid_label}] ({len(all_members)} intents)...", end=" ", flush=True)
                result = llm.call_json(OUTCOME_ASSIGN_SYSTEM, prompt,
                                       max_tokens=8192, model=sonnet_model)

                if result and isinstance(result, dict):
                    for item in result.get("unique_intents", []):
                        outcome = item.get("outcome", "Uncategorized")
                        intent = f"{persona}: {item['intent']}"
                        persona_outcome_intents.setdefault(outcome, []).append(intent)
                        if outcome not in existing_outcomes:
                            existing_outcomes.append(outcome)
                    dropped = result.get("dropped_intents", [])
                    total_dropped += len(dropped)
                    kept = len(result.get("unique_intents", []))
                    print(f"→ {kept} kept, {len(dropped)} dropped, {len(existing_outcomes)} outcomes")
                else:
                    for m in all_members:
                        persona_outcome_intents.setdefault("Uncategorized", []).append(m)
                    print(f"→ fallback, kept all {len(all_members)}")
                time.sleep(3)

            # Process noise (singletons) — sort by embedding similarity for topic-coherent batches
            if noise:
                # Sort singletons so related intents are adjacent
                noise_with_emb = [(m, embeddings.get(m)) for m in noise]
                noise_with_emb_valid = [(m, e) for m, e in noise_with_emb if e is not None]
                noise_no_emb = [m for m, e in noise_with_emb if e is None]

                if noise_with_emb_valid:
                    # Use greedy nearest-neighbor ordering
                    sorted_noise = []
                    remaining = list(noise_with_emb_valid)
                    current = remaining.pop(0)
                    sorted_noise.append(current[0])

                    while remaining:
                        current_emb = np.array(current[1])
                        best_idx = 0
                        best_sim = -1
                        for idx, (m, e) in enumerate(remaining):
                            sim = float(np.dot(current_emb, np.array(e)) /
                                       (np.linalg.norm(current_emb) * np.linalg.norm(np.array(e))))
                            if sim > best_sim:
                                best_sim = sim
                                best_idx = idx
                        current = remaining.pop(best_idx)
                        sorted_noise.append(current[0])

                    sorted_noise.extend(noise_no_emb)
                else:
                    sorted_noise = noise

                print(f"    Singletons sorted by topic similarity for coherent batching")

                for batch_start in range(0, len(sorted_noise), MAX_PER_CALL):
                    batch = sorted_noise[batch_start:batch_start + MAX_PER_CALL]
                    existing_str = _build_existing_context()
                    stripped = [m.split(": ", 1)[-1] for m in batch]

                    prompt = f"""Persona: {persona}

Existing outcomes with their assigned intents (REUSE outcomes, drop intents that duplicate already-assigned ones):
{existing_str}

Remaining intents to process (grouped by topic similarity):
{json.dumps(stripped, indent=2)}

IMPORTANT:
1. Drop any intents that duplicate capabilities already covered by existing outcomes
2. Assign unique intents to existing outcomes or create new ones ONLY if needed"""

                    print(f"    Singleton batch {batch_start//30 + 1} ({len(batch)} intents)...", end=" ", flush=True)
                    result = llm.call_json(OUTCOME_ASSIGN_SYSTEM, prompt,
                                           max_tokens=8192, model=sonnet_model)

                    if result and isinstance(result, dict):
                        for item in result.get("unique_intents", []):
                            outcome = item.get("outcome", "Uncategorized")
                            intent = f"{persona}: {item['intent']}"
                            persona_outcome_intents.setdefault(outcome, []).append(intent)
                            if outcome not in existing_outcomes:
                                existing_outcomes.append(outcome)

                        dropped = result.get("dropped_intents", [])
                        total_dropped += len(dropped)
                        kept = len(result.get("unique_intents", []))
                        print(f"→ {kept} kept, {len(dropped)} dropped")
                    else:
                        for m in batch:
                            persona_outcome_intents.setdefault("Uncategorized", []).append(m)
                        print(f"→ fallback, kept all")

                    time.sleep(3)

            # Build persona structure
            total_unique = sum(len(v) for v in persona_outcome_intents.values())
            total_input = sum(len(v) for v in clusters.values())
            print(f"\n  {persona}: {total_input} → {total_unique} unique across {len(persona_outcome_intents)} outcomes")

            structure.append({
                "persona": persona,
                "outcomes": [
                    {"outcome": oname, "intents": ointents}
                    for oname, ointents in persona_outcome_intents.items()
                ]
            })

        # Present full outcome → intent mapping for review
        print(f"\n{'='*60}")
        print(f"OUTCOME → INTENT MAPPING")
        print(f"{'='*60}")
        print(f"""
  Sonnet processed each cluster and performed two tasks:
    1. DEDUP: Dropped {total_dropped} intents that duplicate other intents
    2. ASSIGN: Mapped each unique intent to a high-level outcome

  Review the mapping below to verify:
    - Outcomes are meaningful business capabilities (not technical)
    - Each outcome has 3-8 outcomes per persona (not too many, not too few)
    - Intents are assigned to the correct outcome
    - No important intents were incorrectly dropped

  After approval, this structure will be upserted to the functional graph
  and Pass 3 will generate scenarios for each outcome.
""")

        total_final = sum(
            len(o.get("intents", []))
            for p in structure for o in p.get("outcomes", [])
        )
        print(f"  Total: {len(structure)} personas, "
              f"{sum(len(p.get('outcomes',[])) for p in structure)} outcomes, "
              f"{total_final} unique intents\n")

        for p in structure:
            persona = p.get("persona", "?")
            outcomes = p.get("outcomes", [])
            p_intents = sum(len(o.get("intents", [])) for o in outcomes)
            print(f"  {'='*56}")
            print(f"  {persona} ({len(outcomes)} outcomes, {p_intents} intents)")
            print(f"  {'='*56}")

            for o in sorted(outcomes, key=lambda x: -len(x.get("intents", []))):
                intents = o.get("intents", [])
                print(f"\n    [{o.get('outcome', '?')}] ({len(intents)} intents)")
                for i in sorted(intents):
                    clean = i.split(": ", 1)[-1] if ": " in i else i
                    print(f"      - {clean}")

        # Feedback loop
        while True:
            action, feedback = ask_user("\nReview the outcome mapping above. [A]pprove to upsert, [E]dit to revise, [S]kip to abort:")
            if action == "approve":
                break
            elif action == "edit":
                print(f"\n  Applying feedback: {feedback}")
                # Build current structure summary for Sonnet
                for p in structure:
                    persona = p.get("persona", "?")
                    outcome_summary = {}
                    for o in p.get("outcomes", []):
                        intents = o.get("intents", [])
                        stripped = [i.split(": ", 1)[-1] for i in intents]
                        sample = stripped[:3]
                        if len(stripped) > 3:
                            sample.append(f"... +{len(stripped) - 3} more")
                        outcome_summary[o["outcome"]] = sample

                    edit_prompt = f"""Persona: {persona}

Current outcome structure:
{json.dumps(outcome_summary, indent=2)}

User feedback:
{feedback}

Apply the user's feedback to restructure the outcomes. You may:
- Remove outcomes (reassign their intents to other outcomes, or drop them)
- Merge outcomes together
- Rename outcomes
- Move intents between outcomes

Return the COMPLETE revised structure (not just the changes).
Every intent must appear in exactly one outcome.

OUTPUT FORMAT (strict JSON):
[{{"outcome": "<name>", "intents": ["intent1", "intent2", ...]}}]
"""
                    print(f"  Revising {persona} outcomes...", end=" ", flush=True)
                    revised = llm.call_json(OUTCOME_ASSIGN_SYSTEM, edit_prompt,
                                            max_tokens=16384, model=sonnet_model)

                    if revised and isinstance(revised, list):
                        # Replace outcomes for this persona
                        p["outcomes"] = [
                            {"outcome": o.get("outcome", ""), "intents": [f"{persona}: {i}" for i in o.get("intents", [])]}
                            for o in revised
                        ]
                        new_count = len(p["outcomes"])
                        new_intents = sum(len(o.get("intents", [])) for o in p["outcomes"])
                        print(f"→ {new_count} outcomes, {new_intents} intents")
                    elif revised and isinstance(revised, dict):
                        # Handle if Sonnet returns {unique_intents, dropped_intents} format
                        new_outcomes = {}
                        for item in revised.get("unique_intents", []):
                            outcome = item.get("outcome", "Uncategorized")
                            intent = f"{persona}: {item['intent']}"
                            new_outcomes.setdefault(outcome, []).append(intent)
                        p["outcomes"] = [
                            {"outcome": oname, "intents": ointents}
                            for oname, ointents in new_outcomes.items()
                        ]
                        print(f"→ {len(p['outcomes'])} outcomes")
                    else:
                        print("→ revision failed, keeping current structure")

                # Re-display revised structure
                print(f"\n{'='*60}")
                print(f"REVISED OUTCOME MAPPING")
                print(f"{'='*60}")
                total_final = sum(
                    len(o.get("intents", []))
                    for p in structure for o in p.get("outcomes", [])
                )
                print(f"\n  Total: {len(structure)} personas, "
                      f"{sum(len(p.get('outcomes',[])) for p in structure)} outcomes, "
                      f"{total_final} unique intents\n")
                for p in structure:
                    persona = p.get("persona", "?")
                    outcomes = p.get("outcomes", [])
                    p_intents = sum(len(o.get("intents", [])) for o in outcomes)
                    print(f"  {'='*56}")
                    print(f"  {persona} ({len(outcomes)} outcomes, {p_intents} intents)")
                    print(f"  {'='*56}")
                    for o in sorted(outcomes, key=lambda x: -len(x.get("intents", []))):
                        intents = o.get("intents", [])
                        print(f"\n    [{o.get('outcome', '?')}] ({len(intents)} intents)")
                        for i in sorted(intents)[:5]:
                            clean = i.split(": ", 1)[-1] if ": " in i else i
                            print(f"      - {clean}")
                        if len(intents) > 5:
                            print(f"      ... +{len(intents) - 5} more")

            elif action == "skip":
                print("Skipping structure creation.")
                return
            elif action == "quit":
                print("Quitting.")
                return

        # Upsert structure (personas + outcomes only); skip personas with no outcomes
        upsert_personas = []
        for p in structure:
            outcomes = [{"outcome": o["outcome"], "scenarios": []} for o in p.get("outcomes", [])]
            if not outcomes:
                log.info(f"  Skipping persona '{p['persona']}' (no outcomes)")
                continue
            upsert_personas.append({"persona": p["persona"], "outcomes": outcomes})

        upsert_log = os.path.join(os.getcwd(), "llm_logs_v4", "upsert_pass2.json")
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

        # Cache Pass 2 results
        save_pass_cache(2, {"structure": structure})

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
    print("PASS 3: Creating scenarios per outcome (intent-driven discovery)")
    print(f"{'='*60}\n")

    INTENT_BATCH_SIZE = 5  # intents per batch for scenario generation

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
        print(f"[{i+1}/{len(outcome_list)}] {persona} > {outcome_name} ({len(outcome_intents)} intents)")
        print(f"{'='*60}")

        try:
            # ---- Step 3a: Search per intent, collect search results ----
            print(f"  Phase 1: Discovering files per intent...")

            intent_search_results = {}  # intent → [search results]
            all_found_paths = {}  # path → {score, data, label} (for file fetching later)

            for ii, intent in enumerate(outcome_intents):
                try:
                    # Multi-query search: intent text + extracted entity keywords
                    all_results = []

                    # Query 1: Full intent text (semantic match)
                    results1 = api.code_graph_search(project_uuid, intent, limit=10)
                    all_results.extend(results1)

                    # Query 2: Extract key nouns/entities from intent for targeted search
                    intent_text = intent.split(": ", 1)[-1] if ": " in intent else intent
                    # Remove common verbs to get entity-focused query
                    entity_query = intent_text
                    for verb in ["Create", "Update", "Delete", "Manage", "Edit", "View",
                                 "Generate", "Process", "Handle", "Retrieve", "Search",
                                 "Configure", "Perform", "Track", "Export", "Import",
                                 "create", "update", "delete", "manage", "edit", "view",
                                 "generate", "process", "handle", "retrieve", "search",
                                 "configure", "perform", "track", "export", "import",
                                 "and", "with", "for", "the", "a", "an", "or", "in",
                                 "to", "from", "by", "on", "at", "of", "comprehensive",
                                 "various", "detailed", "specific", "financial"]:
                        entity_query = entity_query.replace(verb + " ", " ").replace(" " + verb, " ")
                    entity_query = " ".join(entity_query.split()).strip()
                    if entity_query and len(entity_query) > 3:
                        results2 = api.code_graph_search(project_uuid, entity_query, limit=5)
                        all_results.extend(results2)

                    # Deduplicate by path, keep highest score
                    valid_results = []
                    seen_paths = {}
                    for r in all_results:
                        score = r.get("score", 0)
                        data = r.get("data", {})
                        path = data.get("path", "")
                        label = r.get("label", "")
                        if not path or score < 0.25:
                            continue
                        if label in ("File", "Function", "Class"):
                            if path not in seen_paths or score > seen_paths[path]:
                                seen_paths[path] = score
                                valid_results.append(r)
                                if path not in all_found_paths or score > all_found_paths[path]["score"]:
                                    all_found_paths[path] = {"score": score, "data": data, "label": label}

                    intent_search_results[intent] = valid_results
                    result_count = len(valid_results)
                    print(f"    [{ii+1}/{len(outcome_intents)}] {intent} → {result_count} results")
                except Exception as e:
                    intent_search_results[intent] = []
                    log.warning(f"    [{ii+1}/{len(outcome_intents)}] {intent} → error: {e}")

            total_unique_paths = len(all_found_paths)
            print(f"  Discovery complete: {total_unique_paths} unique file paths across {len(outcome_intents)} intents")

            if total_unique_paths == 0:
                print(f"  No relevant files found for any intent, skipping")
                continue

            # ---- Step 3a.2: Fetch file details for matched paths (deduplicated, with children) ----
            print(f"\n  Phase 1b: Fetching file details for {total_unique_paths} unique matched files...")
            outcome_file_details = {}  # path → file detail (fetched once, reused everywhere)

            for path, info in all_found_paths.items():
                if path in outcome_file_details:
                    continue
                try:
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
                        outcome_file_details[path] = items[0]
                except Exception as e:
                    log.warning(f"    Failed to fetch {path}: {e}")

            print(f"  Fetched details for {len(outcome_file_details)} files (with children)")

            # Build enriched summary for scenario generation
            # Group files by which intents matched them for context
            def _get_batch_file_summary(intent_batch):
                """Get format_summary for files matched by intents in this batch."""
                batch_paths = set()
                for intent in intent_batch:
                    for r in intent_search_results.get(intent, []):
                        p = r.get("data", {}).get("path", "")
                        if p:
                            batch_paths.add(p)
                batch_files = [outcome_file_details[p] for p in batch_paths if p in outcome_file_details]
                return format_summary(batch_files) if batch_files else ""

            # ---- Step 3b: Generate scenarios in intent batches ----
            print(f"\n  Phase 2: Generating scenarios in batches of {INTENT_BATCH_SIZE} intents...")

            existing_scenario_names = []  # cumulative — prevents duplicates across batches
            all_batch_scenarios = []  # all scenarios across batches

            intent_batches = [outcome_intents[j:j + INTENT_BATCH_SIZE]
                              for j in range(0, len(outcome_intents), INTENT_BATCH_SIZE)]

            for bi, intent_batch in enumerate(intent_batches):
                print(f"\n    Batch {bi+1}/{len(intent_batches)}: {intent_batch}")

                # Get enriched file summary for this batch's matched files
                batch_file_summary = _get_batch_file_summary(intent_batch)

                if not batch_file_summary:
                    # Fallback to lightweight search results if no file details available
                    batch_context_parts = []
                    for intent in intent_batch:
                        results = intent_search_results.get(intent, [])
                        if results:
                            batch_context_parts.append(format_search_results(intent, results))
                    if not batch_context_parts:
                        print(f"    No search results for this batch, skipping")
                        continue
                    batch_file_summary = "\n\n".join(batch_context_parts)

                # Chunk if summary is too large
                summary_chunks = chunk_text(batch_file_summary, max_chars=80000)

                # Build existing scenarios string for dedup
                existing_scenarios_str = json.dumps(existing_scenario_names) if existing_scenario_names else "[]"

                scenario_prompt = SCENARIO_SYSTEM.format(existing_scenarios=existing_scenarios_str)
                scenario_prompt_with_files = scenario_prompt.replace(
                    '"description": "<brief>"',
                    '"description": "<brief>", "relevant_files": ["<path1>", "<path2>"]'
                )

                # Process each chunk (usually just one unless files are very large)
                for ci, chunk in enumerate(summary_chunks):
                    if len(summary_chunks) > 1:
                        print(f"      Chunk {ci+1}/{len(summary_chunks)} ({len(chunk)} chars)")

                    user_prompt = f"""Create scenarios for the outcome "{outcome_name}" under persona "{persona}".

Capture every distinct user or system flow you can identify from the code below.
Pay attention to each function — if a function represents a distinct user workflow
(e.g., scheduling, drafting, publishing are separate flows), create separate scenarios.

LOCKED Persona: {persona}
LOCKED Outcome: {outcome_name}

Intents in this batch:
{json.dumps(intent_batch, indent=2)}

Code structure (classes, methods, functions with call chains):
{chunk}

For each scenario, include a "relevant_files" array listing the file paths
most relevant to that scenario (for detailed code analysis in the next step).
"""

                print(f"    Extracting scenarios...")
                batch_result = llm.call_json(scenario_prompt_with_files, user_prompt,
                                             max_tokens=8192, model=sonnet_model)

                if batch_result:
                    # Extract scenario names for cumulative dedup
                    for po in batch_result:
                        for oo in po.get("outcomes", []):
                            for so in oo.get("scenarios", []):
                                sname = so.get("scenario", "")
                                if sname and sname not in existing_scenario_names:
                                    existing_scenario_names.append(sname)
                    all_batch_scenarios.extend(batch_result)
                    new_count = sum(len(oo.get("scenarios", []))
                                    for po in batch_result for oo in po.get("outcomes", []))
                    print(f"    → {new_count} scenarios (total unique: {len(existing_scenario_names)})")
                else:
                    print(f"    → no scenarios")

            # Merge all batch results — deduplicate by scenario name
            if not all_batch_scenarios:
                print(f"  No scenarios found across all batches")
                continue

            merged = {}
            for po in all_batch_scenarios:
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

            if not result:
                print(f"  No scenarios after merge")
                continue

            # ---- Step 3c: Generate steps/actions per scenario (Haiku, full file details) ----
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

            print(f"\n  Phase 3: Generating steps/actions for {len(all_sc)} scenarios...")

            # Reuse file details already fetched in Phase 1b — no duplicate API calls
            # For any scenario files not yet fetched, fetch them now
            scenario_file_paths = set()
            for sc in all_sc:
                for fp in sc.get("relevant_files", []):
                    scenario_file_paths.add(fp)

            new_paths = scenario_file_paths - set(outcome_file_details.keys())
            if new_paths:
                print(f"  Fetching {len(new_paths)} additional files not in Phase 1b cache...")
                for path in new_paths:
                    try:
                        details = api._get(f"/code-ontology/{project_uuid}/File", {
                            "filters[path][$eq]": path,
                            "children": "true",
                        })
                        items = details.get("data", [])
                        if items:
                            outcome_file_details[path] = items[0]
                    except Exception as e:
                        log.warning(f"  Failed to fetch {path}: {e}")

            file_details = [outcome_file_details[p] for p in scenario_file_paths if p in outcome_file_details]
            print(f"  Using {len(file_details)} files for step/action generation ({len(outcome_file_details)} total cached)")

            # Build file index for lookup
            details_by_path = {f.get("path", ""): f for f in file_details}

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

                if not relevant_file_data:
                    log.warning(f"  No file details available for scenarios: {[s['scenario'] for s in batch]}")
                    continue

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

            # Attach citations as array of objects (not stringified)
            # CitationInputDto: type (enum: document|exDoc|figma|jira|confluence|code|prompt), name, reference
            def _path_to_citation(path):
                info = all_found_paths.get(path, {})
                # Always use file path as name, never function/class names
                file_path = info.get("data", {}).get("path", path)
                file_id = info.get("data", {}).get("id", path)
                return {"reference": file_id, "name": file_path, "type": "code"}

            all_outcome_paths = list(all_found_paths.keys())
            outcome_citations = [_path_to_citation(p) for p in all_outcome_paths]

            for po in result:
                for oo in po.get("outcomes", []):
                    oo["citations"] = outcome_citations
                    for so in oo.get("scenarios", []):
                        rel_files = so.pop("relevant_files", [])
                        # Filter to only file paths (must contain /), not function/class names
                        rel_files = [f for f in rel_files if '/' in f]
                        scenario_citations = [_path_to_citation(fp) for fp in rel_files] if rel_files else outcome_citations
                        so["citations"] = scenario_citations
                        for step in so.get("steps", []):
                            step["citations"] = scenario_citations
                            for action in step.get("actions", []):
                                action["citations"] = scenario_citations

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
                # Re-run last batch with feedback (simplified — uses all intents)
                scenario_prompt_edit = SCENARIO_SYSTEM.format(existing_scenarios="[]")
                scenario_prompt_edit = scenario_prompt_edit.replace(
                    '"description": "<brief>"',
                    '"description": "<brief>", "relevant_files": ["<path1>", "<path2>"]'
                )
                # Gather all search context
                all_context_parts = []
                for intent in outcome_intents:
                    results = intent_search_results.get(intent, [])
                    if results:
                        all_context_parts.append(format_search_results(intent, results))
                all_context = "\n\n".join(all_context_parts)
                if len(all_context) > 80000:
                    all_context = all_context[:80000] + "\n... (truncated)"

                edit_prompt = f"""Revise scenarios for the outcome "{outcome_name}" under persona "{persona}".

LOCKED Persona: {persona}
LOCKED Outcome: {outcome_name}

All intents:
{json.dumps(outcome_intents, indent=2)}

Code search results:
{all_context}

User feedback on previous proposal:
{feedback}

Revise accordingly. Include "relevant_files" arrays.
"""
                result2 = llm.call_json(scenario_prompt_edit, edit_prompt,
                                        max_tokens=8192, model=sonnet_model)
                if result2:
                    print(f"  Revised:")
                    for po in result2:
                        for oo in po.get("outcomes", []):
                            for so in oo.get("scenarios", []):
                                print(f"    {so['scenario']}")
                    a2, _ = ask_user("Approve revised?")
                    if a2 == "approve":
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

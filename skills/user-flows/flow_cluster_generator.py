"""
Flow Cluster Generator
======================
Generates flow-based cluster documents from BreezeAI code ontology graph.
Instead of Louvain clusters (grouped by code similarity), this groups files
by user flow — tracing from entry points (pages/controllers) through
service hooks, controllers, services, and data layers.

Usage:
    python flow_cluster_generator.py
    python flow_cluster_generator.py --project-uuid <uuid>
    python flow_cluster_generator.py --project-uuid <uuid> --output-dir ./output
    python flow_cluster_generator.py --project-uuid <uuid> --entry-point "knowledge-management"
"""

import json
import os
import re
import sys
import argparse
import math
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

import requests


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_API_BASE = "https://isometric-backend.accionbreeze.com"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
AUTH_HEADER_NAME = "api-key"
BREEZE_CONFIG_FILE = ".breeze.json"
MAX_TRACE_DEPTH = 4
MAX_FILES_PER_FLOW = 20

# Paths to skip when tracing (cross-cutting / utility)
SKIP_PATH_PATTERNS = [
    r"node_modules",
    r"configs?/",
    r"constants",
    r"enums/index",
    r"entities/.*\.entity\.",  # entity definitions (keep services that USE them)
    r"graph-entities/",
    r"middlewares?/",
    r"__tests?__",
    r"\.spec\.",
    r"\.test\.",
]

# ---------------------------------------------------------------------------
# Entry point detection patterns (language-agnostic)
# ---------------------------------------------------------------------------

# Backend entry points — files containing route handlers
BACKEND_ENTRY_PATTERNS = [
    r"controller",          # Express/NestJS/Spring/.NET
    r"handler",             # Generic handlers
    r"views?\.(py|php)$",   # Django views, PHP views
    r"viewsets?\.",          # Django REST viewsets
    r"routers?/",           # FastAPI routers
    r"endpoints?/",         # Generic endpoints
]

# Frontend entry points — page-level components
FRONTEND_PAGE_PATTERNS = [
    r"pages?/",             # React/Vue/Angular pages
    r"views?/",             # Vue views
    r"screens?/",           # React Native screens
    r"\.page\.",            # Angular pages
]

# Service/API client layer — bridges frontend to backend
SERVICE_HOOK_PATTERNS = [
    r"service-hooks?/",     # React service hooks
    r"composables?/",       # Vue composables
    r"services?/.*\.service\.", # Angular services
    r"api/",                # API client layer
    r"hooks?/use",          # React hooks
]

# Route decorator patterns (for identifying backend entry methods)
ROUTE_DECORATOR_PATTERNS = [
    r"@(Get|Post|Put|Delete|Patch)\s*\(",           # Express/NestJS
    r"\[(Http(Get|Post|Put|Delete|Patch))",          # .NET
    r"@(GetMapping|PostMapping|PutMapping|DeleteMapping|RequestMapping)",  # Spring
    r"@(api_view|action|app\.(get|post)|router\.(get|post))",  # Python
    r"Route::(get|post|put|delete|resource)",         # PHP Laravel
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FileInfo:
    """Represents a file from the code graph with its full details."""
    id: str
    path: str
    name: str
    repository_name: str
    language: str
    loc: int
    cluster_id: int
    imports: list = field(default_factory=list)
    external_imports: list = field(default_factory=list)
    functions: list = field(default_factory=list)
    classes: list = field(default_factory=list)
    statements: list = field(default_factory=list)
    code_ontology_id: int = 0
    imported_by_count: int = 0
    import_count: int = 0


@dataclass
class FlowCluster:
    """A flow cluster groups files that participate in the same user flow."""
    name: str
    entry_point: str
    flow_type: str  # UI_TO_BACKEND, BACKEND_ONLY, UI_ONLY
    frontend_files: list = field(default_factory=list)
    backend_files: list = field(default_factory=list)
    cross_references: list = field(default_factory=list)
    async_boundaries: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# API Client
# ---------------------------------------------------------------------------

class BreezeAPIClient:
    """Client for BreezeAI backend APIs."""

    def __init__(self, api_base: str, api_key: str):
        self.api_base = api_base.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            AUTH_HEADER_NAME: api_key,
            "Content-Type": "application/json",
        })

    def get_code_ontologies(self, project_uuid: str) -> list[dict]:
        """Get all code ontology records for a project."""
        url = f"{self.api_base}/code-ontology/"
        params = {
            "filters[projectUuid][$eq]": project_uuid,
            "page": 1,
            "limit": 50,
        }
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])

    def get_all_files(
        self, project_uuid: str, code_ontology_id: int, with_children: bool = True
    ) -> list[dict]:
        """Fetch all File nodes for a code ontology, paginated."""
        all_files = []
        page = 1
        limit = 100

        while True:
            url = f"{self.api_base}/code-ontology/{project_uuid}/File"
            params = {
                "page": page,
                "limit": limit,
                "sortName": "path",
                "sortOrder": "asc",
                "children": "true" if with_children else "false",
                "filters[codeOntologyId][$eq]": code_ontology_id,
            }
            resp = self.session.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

            items = data.get("data", [])
            all_files.extend(items)

            total = data.get("total", 0)
            if page * limit >= total or len(items) == 0:
                break
            page += 1

        return all_files


# ---------------------------------------------------------------------------
# File parsing
# ---------------------------------------------------------------------------

def parse_file(raw: dict) -> FileInfo:
    """Parse raw API response into a FileInfo object."""
    # Parse imports from embeddingText if not directly available
    embedding_text = raw.get("embeddingText", "")
    imports_list = []
    if "Imports:" in embedding_text:
        imports_line = embedding_text.split("Imports:")[1].split("\n")[0].strip()
        imports_list = [i.strip() for i in imports_line.split(",") if i.strip()]

    return FileInfo(
        id=raw.get("id", ""),
        path=raw.get("path", ""),
        name=raw.get("name", ""),
        repository_name=raw.get("repositoryName", ""),
        language=raw.get("language", ""),
        loc=raw.get("loc", 0),
        cluster_id=raw.get("clusterId", 0),
        imports=imports_list,
        external_imports=raw.get("externalImports", []),
        functions=raw.get("functions", []),
        classes=raw.get("classes", []),
        statements=raw.get("statements", []) if isinstance(raw.get("statements"), list) else [],
        code_ontology_id=raw.get("codeOntologyId", 0),
        imported_by_count=raw.get("importedByCount", 0),
        import_count=raw.get("importCount", 0),
    )


def extract_calls_paths(file_info: FileInfo) -> set[str]:
    """Extract all cross-file call paths from a file's functions and class methods."""
    paths = set()

    def _extract_from_calls_json(calls_str):
        if not calls_str:
            return
        try:
            calls = json.loads(calls_str) if isinstance(calls_str, str) else calls_str
        except (json.JSONDecodeError, TypeError):
            return
        for call in calls:
            if isinstance(call, dict) and call.get("path"):
                p = call["path"]
                # Skip external packages and self-references
                if not p.startswith("@") and not p.startswith("node_modules") and "/" in p:
                    paths.add(p)

    # Functions
    for fn in file_info.functions:
        _extract_from_calls_json(fn.get("calls", "[]"))

    # Class methods
    for cls in file_info.classes:
        for method in cls.get("methods", []):
            _extract_from_calls_json(method.get("calls", "[]"))

    return paths


# ---------------------------------------------------------------------------
# Entry point detection (multi-layer, language-agnostic)
# ---------------------------------------------------------------------------

# Route decorator/annotation patterns found in statement text (Layer 1)
# These are captured as Statement nodes in the code graph for any language
ROUTE_STATEMENT_PATTERNS = re.compile(
    r"("
    # TypeScript/NestJS/Express decorators
    r"@(Get|Post|Put|Delete|Patch|All)\s*\("
    # Java/Spring annotations
    r"|@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)\b"
    r"|@RestController\b"
    # .NET attributes
    r"|\[(Http(Get|Post|Put|Delete|Patch)|ApiController|Route)\b"
    # Python/FastAPI decorators
    r"|@(router|app)\.(get|post|put|delete|patch)\s*\("
    # Python/Django decorators
    r"|@api_view\s*\("
    r"|@action\s*\("
    # PHP/Laravel route definitions
    r"|Route::(get|post|put|delete|patch|resource|middleware)\s*\("
    # Go route registrations (in statement text)
    r"|r\.(GET|POST|PUT|DELETE|PATCH|Handle)\s*\("
    # ASP.NET Minimal API
    r"|app\.Map(Get|Post|Put|Delete|Patch)\s*\("
    # Flask
    r"|@app\.route\s*\("
    r")",
    re.IGNORECASE,
)


def _get_all_statements_text(f: FileInfo) -> list[str]:
    """Extract all statement text from a file (file-level, class-level, method-level)."""
    texts = []

    # File-level statements
    for stmt in f.statements:
        if isinstance(stmt, dict):
            texts.append(stmt.get("text", ""))
        elif isinstance(stmt, str):
            texts.append(stmt)

    # Class-level statements and method statements
    for cls in f.classes:
        for stmt in cls.get("statements", []):
            if isinstance(stmt, dict):
                texts.append(stmt.get("text", ""))
        for method in cls.get("methods", []):
            for stmt in method.get("statements", []):
                if isinstance(stmt, dict):
                    texts.append(stmt.get("text", ""))

    return texts


def _has_route_statements(f: FileInfo) -> bool:
    """Layer 1: Check if file has route decorators/annotations in its statements."""
    for text in _get_all_statements_text(f):
        if ROUTE_STATEMENT_PATTERNS.search(text):
            return True
    return False


def _matches_backend_path(f: FileInfo) -> bool:
    """Layer 2: Check if file path matches backend entry point conventions."""
    return any(re.search(p, f.path, re.IGNORECASE) for p in BACKEND_ENTRY_PATTERNS)


def _matches_frontend_path(f: FileInfo) -> bool:
    """Layer 2: Check if file path matches frontend page conventions."""
    if any(re.search(p, f.path, re.IGNORECASE) for p in FRONTEND_PAGE_PATTERNS):
        # Exclude shared components
        if not re.search(r"(elements?|ui|layout|widgets?|common)/", f.path, re.IGNORECASE):
            return True
    return False


def _is_structural_entry_point(f: FileInfo) -> bool:
    """Layer 3: Structural detection — high outbound calls, low inbound calls."""
    total_outbound = 0

    for fn in f.functions:
        try:
            calls = json.loads(fn.get("calls", "[]")) if isinstance(fn.get("calls"), str) else fn.get("calls", [])
        except (json.JSONDecodeError, TypeError):
            calls = []
        total_outbound += len([c for c in calls if isinstance(c, dict) and c.get("path")])

    for cls in f.classes:
        for method in cls.get("methods", []):
            try:
                calls = json.loads(method.get("calls", "[]")) if isinstance(method.get("calls"), str) else method.get("calls", [])
            except (json.JSONDecodeError, TypeError):
                calls = []
            total_outbound += len([c for c in calls if isinstance(c, dict) and c.get("path")])

    # Entry points: many outbound calls (orchestrators) + few files importing them
    return total_outbound >= 3 and f.imported_by_count <= 2


def is_frontend_repo(files: list[FileInfo]) -> bool:
    """Detect if a set of files is from a frontend repo."""
    sample_paths = " ".join(f.path for f in files[:100])
    # Frontend signals: components, pages, hooks, JSX/TSX, package.json with react/angular/vue
    frontend_signals = len(re.findall(
        r"(components?|pages?|hooks?|service-hooks?|\.tsx|\.jsx|\.vue|\.svelte)",
        sample_paths, re.IGNORECASE
    ))
    backend_signals = len(re.findall(
        r"(controllers?|services?/(?!hooks)|repositories|migrations?|\.entity\.)",
        sample_paths, re.IGNORECASE
    ))
    return frontend_signals > backend_signals


def is_backend_repo(files: list[FileInfo]) -> bool:
    """Detect if a set of files is from a backend repo."""
    return not is_frontend_repo(files)


def find_frontend_entry_points(files: list[FileInfo]) -> list[FileInfo]:
    """Find frontend page entry points using multi-layer detection."""
    entries = []
    seen = set()

    for f in files:
        if f.path in seen:
            continue

        # Layer 2: Path-based (pages/, views/, screens/)
        if _matches_frontend_path(f):
            entries.append(f)
            seen.add(f.path)
            continue

        # Layer 3: Structural — file-based routing (Next.js, Nuxt, SvelteKit)
        # Files in app/ or pages/ with low importedByCount are likely page routes
        if re.search(r"(app|pages?)/", f.path, re.IGNORECASE) and f.imported_by_count <= 1:
            if not re.search(r"(layout|error|loading|template)\.", f.path, re.IGNORECASE):
                entries.append(f)
                seen.add(f.path)

    return entries


def find_backend_entry_points(files: list[FileInfo]) -> list[FileInfo]:
    """Find backend controller/handler entry points using multi-layer detection."""
    entries = []
    seen = set()

    for f in files:
        if f.path in seen:
            continue

        # Layer 1: Statement-based (route decorators/annotations)
        # This catches ANY language with route decorators
        if _has_route_statements(f):
            entries.append(f)
            seen.add(f.path)
            continue

        # Layer 2: Path-based (controller, handler, endpoint, etc.)
        if _matches_backend_path(f):
            entries.append(f)
            seen.add(f.path)
            continue

    # Layer 3: Structural fallback — if no entry points found via Layer 1 & 2,
    # use graph structure (high outbound, low inbound)
    if not entries:
        for f in files:
            if f.path in seen:
                continue
            if _is_structural_entry_point(f):
                # Extra check: skip obvious non-entry files
                if not re.search(r"(utils?|helpers?|lib|configs?|entities?|models?)/", f.path, re.IGNORECASE):
                    entries.append(f)
                    seen.add(f.path)

    return entries


def find_service_hooks(files: list[FileInfo]) -> list[FileInfo]:
    """Find frontend service hook files."""
    hooks = []
    for f in files:
        if any(re.search(p, f.path, re.IGNORECASE) for p in SERVICE_HOOK_PATTERNS):
            hooks.append(f)
    return hooks


# ---------------------------------------------------------------------------
# Flow tracing
# ---------------------------------------------------------------------------

def should_skip_path(path: str) -> bool:
    """Check if a file path should be skipped during tracing."""
    return any(re.search(p, path, re.IGNORECASE) for p in SKIP_PATH_PATTERNS)


# Patterns for files we trace THROUGH but don't include in the cluster
PASS_THROUGH_PATTERNS = [
    r"components?/(ui|elements|layout|common|widgets?|panels?|flow)/",
    r"components?/(functional-ontology|manage-access|dashboard|auth)/",
]


def _is_pass_through(path: str) -> bool:
    """Check if a file should be traced through but not included in the cluster."""
    return any(re.search(p, path, re.IGNORECASE) for p in PASS_THROUGH_PATTERNS)


def trace_flow(
    entry_file: FileInfo,
    all_files_by_path: dict[str, FileInfo],
    max_depth: int = 4,
    max_files: int = 20,
) -> list[FileInfo]:
    """Trace the call chain from an entry point file, collecting all related files.

    Traces THROUGH UI sub-components to find the service hooks they import,
    but doesn't include the sub-components themselves in the result.
    """
    visited = set()
    result = []

    def _trace(file_info: FileInfo, depth: int):
        if depth > max_depth or file_info.path in visited or len(result) >= max_files:
            return
        visited.add(file_info.path)

        # Decide whether to include this file in the result or just pass through it
        is_pass_through = _is_pass_through(file_info.path)
        if not is_pass_through:
            result.append(file_info)

        # Always follow CALLS paths — even for pass-through files
        call_paths = extract_calls_paths(file_info)
        for call_path in call_paths:
            if call_path in visited or should_skip_path(call_path):
                continue
            target = all_files_by_path.get(call_path)
            if target:
                _trace(target, depth + 1)

        # Always follow imports — trace through sub-components to find service hooks
        for imp in file_info.imports:
            if imp in visited:
                continue
            target = all_files_by_path.get(imp)
            if not target:
                continue

            # Always follow service hooks / context / hook imports
            if any(re.search(p, imp, re.IGNORECASE) for p in SERVICE_HOOK_PATTERNS):
                _trace(target, depth + 1)
            # Follow sub-components (pass through them to find their service hooks)
            elif _is_pass_through(imp) and not should_skip_path(imp):
                _trace(target, depth + 1)
            # Follow context providers (they often wire up services)
            elif re.search(r"context/", imp, re.IGNORECASE):
                _trace(target, depth + 1)
            # Follow custom hooks (they often wrap service hooks)
            elif re.search(r"hooks?/", imp, re.IGNORECASE):
                _trace(target, depth + 1)

    _trace(entry_file, 0)
    return result


def extract_entity_name(file_path: str) -> str:
    """Extract the entity/domain name from a file path."""
    name = file_path.split("/")[-1]
    # Strip common prefixes/suffixes
    name = re.sub(r"^use-?(get|delete|save|update|search|create)-?", "", name, flags=re.IGNORECASE)
    name = re.sub(r"-(service|controller|handler|repository).*$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\.(ts|js|py|php|java|cs|go|rb|tsx|jsx)x?$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"(Controller|Service|Repository|ViewSet|Handler)$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\.", "", name)
    return name.lower().strip("-_")


def match_backend_for_frontend(
    frontend_files: list[FileInfo],
    backend_files_by_path: dict[str, FileInfo],
    all_backend_files: list[FileInfo],
) -> list[FileInfo]:
    """Find backend files that correspond to frontend service hooks."""
    # Extract entity names from frontend service hooks
    entity_names = set()
    for f in frontend_files:
        if any(re.search(p, f.path, re.IGNORECASE) for p in SERVICE_HOOK_PATTERNS):
            entity = extract_entity_name(f.path)
            if entity and entity not in ("auth", "headers"):
                entity_names.add(entity)

    # Find matching backend controllers
    matched = []
    for entity in entity_names:
        for bf in all_backend_files:
            bf_entity = extract_entity_name(bf.path)
            # Match by entity name
            if bf_entity and (
                entity in bf_entity
                or bf_entity in entity
                or _fuzzy_match(entity, bf_entity)
            ):
                if bf.path not in {f.path for f in matched}:
                    matched.append(bf)

    # For each matched controller, trace its downstream services
    backend_traced = []
    for ctrl in matched:
        traced = trace_flow(ctrl, backend_files_by_path, max_depth=3, max_files=15)
        for f in traced:
            if f.path not in {t.path for t in backend_traced}:
                backend_traced.append(f)

    return backend_traced


def _fuzzy_match(a: str, b: str) -> bool:
    """Simple fuzzy match — checks if names share significant tokens."""
    tokens_a = set(re.split(r"[-_]", a))
    tokens_b = set(re.split(r"[-_]", b))
    tokens_a.discard("")
    tokens_b.discard("")
    if not tokens_a or not tokens_b:
        return False
    overlap = tokens_a & tokens_b
    return len(overlap) / min(len(tokens_a), len(tokens_b)) > 0.5


# ---------------------------------------------------------------------------
# Flow cluster building
# ---------------------------------------------------------------------------

def build_flow_clusters(
    project_uuid: str,
    frontend_files: list[FileInfo],
    backend_files: list[FileInfo],
    entry_point_filter: Optional[str] = None,
) -> list[FlowCluster]:
    """Build flow clusters from detected entry points."""
    clusters = []

    # Index files by path for fast lookup
    fe_by_path = {f.path: f for f in frontend_files}
    be_by_path = {f.path: f for f in backend_files}
    all_by_path = {**fe_by_path, **be_by_path}

    has_frontend = len(frontend_files) > 0
    has_backend = len(backend_files) > 0

    if has_frontend:
        # Mode 1/2: Start from frontend pages
        pages = find_frontend_entry_points(frontend_files)

        for page in pages:
            page_name = extract_entity_name(page.path)

            # Apply filter if specified
            if entry_point_filter and entry_point_filter.lower() not in page.path.lower():
                continue

            print(f"  Tracing frontend flow: {page.path}")

            # Trace frontend side (page → service hooks)
            fe_flow = trace_flow(page, fe_by_path, max_depth=2, max_files=10)

            if has_backend:
                # Mode 1: Cross-repo — match backend files
                be_flow = match_backend_for_frontend(fe_flow, be_by_path, backend_files)
                flow_type = "UI_TO_BACKEND"
            else:
                # Mode 2: Frontend only
                be_flow = []
                flow_type = "UI_ONLY"

            cluster = FlowCluster(
                name=_humanize_name(page_name or page.name),
                entry_point=page.path,
                flow_type=flow_type,
                frontend_files=fe_flow,
                backend_files=be_flow,
            )
            clusters.append(cluster)

    if has_backend:
        # Find backend controllers not already covered by frontend flows
        covered_be_paths = set()
        for c in clusters:
            for f in c.backend_files:
                covered_be_paths.add(f.path)

        controllers = find_backend_entry_points(backend_files)
        for ctrl in controllers:
            if ctrl.path in covered_be_paths:
                continue

            if entry_point_filter and entry_point_filter.lower() not in ctrl.path.lower():
                continue

            print(f"  Tracing backend flow: {ctrl.path}")

            be_flow = trace_flow(ctrl, be_by_path, max_depth=3, max_files=15)

            cluster = FlowCluster(
                name=_humanize_name(extract_entity_name(ctrl.path) or ctrl.name),
                entry_point=ctrl.path,
                flow_type="BACKEND_ONLY",
                frontend_files=[],
                backend_files=be_flow,
            )
            clusters.append(cluster)

    return clusters


def _humanize_name(name: str) -> str:
    """Convert entity name to human-readable flow name."""
    name = re.sub(r"[-_]", " ", name)
    return name.title().strip()


# ---------------------------------------------------------------------------
# Cross-reference detection
# ---------------------------------------------------------------------------

def detect_cross_references(cluster: FlowCluster) -> list[str]:
    """Detect frontend → backend API mappings from the cluster files."""
    refs = []
    for fe_file in cluster.frontend_files:
        for fn in fe_file.functions:
            fn_name = fn.get("name", "")
            calls_str = fn.get("calls", "[]")
            try:
                calls = json.loads(calls_str) if isinstance(calls_str, str) else calls_str
            except (json.JSONDecodeError, TypeError):
                continue

            has_api_call = any(
                c.get("name") in ("apiFetch", "fetch", "axios", "post", "get", "put", "delete")
                or (c.get("path") or "").startswith("@/lib/api")
                for c in calls
                if isinstance(c, dict)
            )
            if has_api_call:
                # Try to find the URL from statements
                for stmt in fn.get("statements", []):
                    text = stmt.get("text", "")
                    if "url" in text.lower() and ("/" in text or "api" in text.lower()):
                        refs.append(f"- {fn_name} --> {text.strip()[:120]}")
                        break
                else:
                    refs.append(f"- {fn_name} --> (API call detected)")

    return refs


def detect_async_boundaries(cluster: FlowCluster) -> list[str]:
    """Detect async processing patterns in the cluster."""
    boundaries = []
    all_files = cluster.frontend_files + cluster.backend_files

    for f_info in all_files:
        all_fns = list(f_info.functions)
        for cls in f_info.classes:
            all_fns.extend(cls.get("methods", []))

        for fn in all_fns:
            fn_name = fn.get("name", "")
            calls_str = fn.get("calls", "[]")
            try:
                calls = json.loads(calls_str) if isinstance(calls_str, str) else calls_str
            except (json.JSONDecodeError, TypeError):
                continue

            # Detect async patterns
            call_names = [c.get("name", "") for c in calls if isinstance(c, dict)]

            if any("Async" in name for name in call_names):
                async_call = next(n for n in call_names if "Async" in n)
                boundaries.append(f"- {fn_name}: Fires {async_call} asynchronously (fire-and-forget)")

            if any("addToQueue" in name for name in call_names):
                boundaries.append(f"- {fn_name}: Queues work via addToQueue (async processing)")

            if any("Workflow" in name for name in call_names):
                wf = next(n for n in call_names if "Workflow" in n)
                boundaries.append(f"- {fn_name}: Triggers {wf} (workflow-based async)")

        # Check for polling patterns in statements
        for stmt in f_info.statements:
            text = stmt.get("text", "") if isinstance(stmt, dict) else ""
            if "REFETCH_INTERVAL" in text or "refetchInterval" in text:
                boundaries.append(f"- {f_info.name}: Frontend polls for status updates via refetchInterval")

    return list(set(boundaries))  # dedupe


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

def format_flow_cluster(cluster: FlowCluster) -> str:
    """Format a flow cluster as a markdown document."""
    lines = []

    lines.append(f"# {cluster.name} — Flow Cluster Document")
    lines.append("")
    lines.append(f"Flow Type: {cluster.flow_type}")
    lines.append(f"Entry Point: {cluster.entry_point}")
    total = len(cluster.frontend_files) + len(cluster.backend_files)
    lines.append(f"Total Files: {total} | Frontend: {len(cluster.frontend_files)} | Backend: {len(cluster.backend_files)}")
    lines.append("")

    # Frontend files
    file_num = 0
    for f in cluster.frontend_files:
        file_num += 1
        lines.extend(_format_file_section(f, file_num))

    # Backend files
    for f in cluster.backend_files:
        file_num += 1
        lines.extend(_format_file_section(f, file_num))

    # Cross-reference
    refs = detect_cross_references(cluster)
    lines.append("=" * 80)
    lines.append("CROSS-REFERENCE: Frontend to Backend")
    lines.append("=" * 80)
    lines.append("")
    if refs:
        for ref in refs:
            lines.append(ref)
    else:
        lines.append("(No cross-references detected)")
    lines.append("")

    # Async boundaries
    boundaries = detect_async_boundaries(cluster)
    lines.append("=" * 80)
    lines.append("ASYNC BOUNDARIES")
    lines.append("=" * 80)
    lines.append("")
    if boundaries:
        for b in boundaries:
            lines.append(b)
    else:
        lines.append("(No async boundaries detected)")
    lines.append("")

    return "\n".join(lines)


def _format_file_section(f: FileInfo, num: int) -> list[str]:
    """Format a single file section."""
    lines = []
    lines.append("=" * 80)
    lines.append(f"FILE: {f.path}")
    lines.append("=" * 80)
    lines.append(f"Repository: {f.repository_name} | LOC: {f.loc} | Language: {f.language} | Cluster: {f.cluster_id}")
    lines.append("")

    # Imports
    if f.imports:
        lines.append("Imports:")
        for imp in f.imports:
            lines.append(f"- {imp}")
        lines.append("")

    # External dependencies
    if f.external_imports:
        lines.append(f"External: {', '.join(f.external_imports)}")
        lines.append("")

    # Classes
    for cls in f.classes:
        cls_name = cls.get("name", "Unknown")
        start = cls.get("startLine", "?")
        end = cls.get("endLine", "?")
        vis = cls.get("visibility", "public")
        abstract = cls.get("isAbstract", False)
        cls_type = cls.get("type", "class")

        if cls_type == "interface":
            lines.append(f"Interface: {cls_name} (Lines: {start}-{end})")
        else:
            lines.append(f"Class: {cls_name} (Lines: {start}-{end}) | {vis} | Abstract: {abstract}")
        lines.append("")

        # Class statements
        cls_stmts = cls.get("statements", [])
        if cls_stmts:
            lines.append("  Class Statements:")
            for stmt in cls_stmts:
                _append_statement(lines, stmt, indent="  ")
            lines.append("")

        # Methods
        methods = cls.get("methods", [])
        if methods:
            lines.append("  Methods:")
            lines.append("")
            for method in methods:
                _append_function(lines, method, indent="  ")

    # Standalone functions
    if f.functions:
        lines.append("Functions:")
        lines.append("")
        for fn in f.functions:
            _append_function(lines, fn, indent="")

    # File-level statements
    if f.statements:
        lines.append("File-Level Statements:")
        for stmt in f.statements:
            _append_statement(lines, stmt, indent="")
        lines.append("")

    return lines


def _append_function(lines: list, fn: dict, indent: str = ""):
    """Append a function/method entry."""
    name = fn.get("name", "unknown")
    params = fn.get("params", [])
    params_str = ", ".join(params) if isinstance(params, list) else str(params)
    fn_type = fn.get("type", "")
    start = fn.get("startLine", "?")
    end = fn.get("endLine", "?")

    lines.append(f"{indent}- {name}({params_str}) | {fn_type} | Lines: {start}-{end}")

    # Calls
    calls_str = fn.get("calls", "[]")
    try:
        calls = json.loads(calls_str) if isinstance(calls_str, str) else calls_str
    except (json.JSONDecodeError, TypeError):
        calls = []

    if calls:
        call_parts = []
        for c in calls:
            if isinstance(c, dict):
                cname = c.get("name", "?")
                cpath = c.get("path")
                if cpath:
                    call_parts.append(f"{cname} ({cpath})")
                else:
                    call_parts.append(cname)
        lines.append(f"{indent}  Calls: {', '.join(call_parts)}")

    # Statements
    stmts = fn.get("statements", [])
    if stmts:
        lines.append(f"{indent}  Statements:")
        for stmt in stmts:
            _append_statement(lines, stmt, indent=f"{indent}  ")

    lines.append("")


def _append_statement(lines: list, stmt: dict, indent: str = ""):
    """Append a statement entry."""
    if isinstance(stmt, str):
        # Handle string statements (from embeddingText parsing)
        try:
            stmt = json.loads(stmt)
        except (json.JSONDecodeError, TypeError):
            lines.append(f"{indent}- {stmt}")
            return

    stype = stmt.get("type", "unknown")
    text = stmt.get("text", "").replace("\r\n", " ").replace("\n", " ")
    start = stmt.get("startLine", "?")
    end = stmt.get("endLine", start)

    if start == end:
        lines.append(f"{indent}- [{stype}] (line {start}): {text}")
    else:
        lines.append(f"{indent}- [{stype}] (line {start}-{end}): {text}")


# ---------------------------------------------------------------------------
# Orphan file detection
# ---------------------------------------------------------------------------

ORPHAN_CATEGORIES = {
    "entities": r"\.entity\.|entities/|models/|\.model\.",
    "config": r"configs?/|\.config\.|environment|settings|nodemon|tsconfig|package|Dockerfile|\.yaml$|\.json$|\.gitignore|\.d\.ts$|swagger",
    "types": r"types?/|interfaces?/|enums?/|\.dto\.|\.type\.",
    "graph_entities": r"graph-entities/",
    "ui_components": r"components?/(ui|elements|layout|common|widgets?|panels?|flow|manage-access|functional-ontology|dashboard)/",
    "tests": r"\.(spec|test)\.|__tests?__/|\.stories\.",
    "styles": r"\.(css|scss|less|styled)\.|styles?/",
    "assets": r"assets?/|images?/|icons?/|fonts?/|node_modules/",
    "validations": r"validations?/",
    "context": r"context/",
    "hooks": r"hooks?/(?!.*service)",
    "routes_infra": r"routes?\.(ts|js|tsx)$|routes?/index|protected-route|core\.ts|app\.ts|server\.ts|main\.tsx|index\.ts$|generate-swagger|migrations?/",
    "service_hooks": r"service-hooks?/",
    "utils": r"utils?/|helpers?/|lib/",
    "middleware": r"middlewares?/|interceptors?/|guards?/|pipes?/|filters?/",
    "services": r"services?/|workflows?/|agents?/|workers?/|jobs?/|cron/|queue/|consumers?/",
}


def find_orphan_files(
    all_files: list[FileInfo], flow_clusters: list[FlowCluster]
) -> dict[str, list[FileInfo]]:
    """Find files not covered by any flow cluster and categorize them."""
    covered_paths = set()
    for cluster in flow_clusters:
        for f in cluster.frontend_files + cluster.backend_files:
            covered_paths.add(f.path)

    orphans = [f for f in all_files if f.path not in covered_paths]

    categories = {cat: [] for cat in ORPHAN_CATEGORIES}
    categories["unknown"] = []

    for f in orphans:
        matched = False
        for cat, pattern in ORPHAN_CATEGORIES.items():
            if re.search(pattern, f.path, re.IGNORECASE):
                categories[cat].append(f)
                matched = True
                break
        if not matched:
            categories["unknown"].append(f)

    return categories


MIN_FILES_PER_CLUSTER = 15


def build_orphan_clusters_by_cluster_id(
    all_files: list[FileInfo], flow_clusters: list[FlowCluster]
) -> list[FlowCluster]:
    """Build clusters from ALL orphan files, grouped by Louvain cluster ID.

    Small clusters (< MIN_FILES_PER_CLUSTER) are merged together until
    they reach the minimum threshold.
    """
    covered_paths = set()
    for cluster in flow_clusters:
        for f in cluster.frontend_files + cluster.backend_files:
            covered_paths.add(f.path)

    orphans = [f for f in all_files if f.path not in covered_paths]

    if not orphans:
        return []

    # Group by cluster ID
    by_cluster_id: dict[int, list[FileInfo]] = {}
    for f in orphans:
        cid = f.cluster_id
        if cid not in by_cluster_id:
            by_cluster_id[cid] = []
        by_cluster_id[cid].append(f)

    # Separate into large enough clusters and small clusters that need merging
    large_groups = []   # already >= MIN_FILES_PER_CLUSTER
    small_groups = []   # need to be merged

    for cid, files in sorted(by_cluster_id.items()):
        if len(files) >= MIN_FILES_PER_CLUSTER:
            large_groups.append((cid, files))
        else:
            small_groups.append((cid, files))

    # Merge small groups together until each merged group has >= MIN_FILES_PER_CLUSTER
    merged_groups = []
    current_ids = []
    current_files = []

    for cid, files in small_groups:
        current_ids.append(str(cid))
        current_files.extend(files)

        if len(current_files) >= MIN_FILES_PER_CLUSTER:
            merged_groups.append((current_ids[:], current_files[:]))
            current_ids = []
            current_files = []

    # Handle leftover small group — merge with last merged group if possible
    if current_files:
        if merged_groups:
            # Append to the last merged group
            last_ids, last_files = merged_groups[-1]
            last_ids.extend(current_ids)
            last_files.extend(current_files)
            merged_groups[-1] = (last_ids, last_files)
        else:
            # No merged groups yet — just create one even if under threshold
            merged_groups.append((current_ids, current_files))

    # Build FlowCluster objects
    result = []

    # Large clusters — one per Louvain cluster ID
    for cid, files in large_groups:
        repos = set(f.repository_name for f in files)
        repo_label = " + ".join(sorted(repos))
        frontend = [f for f in files if _is_frontend_file(f)]
        backend = [f for f in files if not _is_frontend_file(f)]

        cluster = FlowCluster(
            name=f"Remaining Cluster {cid} ({repo_label})",
            entry_point=f"(Louvain cluster {cid} — files not covered by flow tracing)",
            flow_type="REMAINING",
            frontend_files=frontend,
            backend_files=backend,
        )
        result.append(cluster)

    # Merged small clusters
    for cluster_ids, files in merged_groups:
        repos = set(f.repository_name for f in files)
        repo_label = " + ".join(sorted(repos))
        ids_label = "+".join(cluster_ids[:5])
        if len(cluster_ids) > 5:
            ids_label += f"+{len(cluster_ids)-5}more"

        frontend = [f for f in files if _is_frontend_file(f)]
        backend = [f for f in files if not _is_frontend_file(f)]

        cluster = FlowCluster(
            name=f"Remaining Clusters {ids_label} ({repo_label})",
            entry_point=f"(Louvain clusters {', '.join(cluster_ids)} — merged small clusters, files not covered by flow tracing)",
            flow_type="REMAINING",
            frontend_files=frontend,
            backend_files=backend,
        )
        result.append(cluster)

    return result


def _is_frontend_file(f: FileInfo) -> bool:
    """Simple check if a file is frontend based on path patterns."""
    return bool(re.search(
        r"(components?|pages?|hooks?|service-hooks?|context|views?)/",
        f.path, re.IGNORECASE
    ))


def format_orphan_report(
    orphan_categories: dict[str, list[FileInfo]], total_files: int, covered_count: int
) -> str:
    """Format the orphan report as text."""
    lines = []
    lines.append("=" * 80)
    lines.append("ORPHAN FILE REPORT")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Total files: {total_files}")
    lines.append(f"Covered by flow clusters: {covered_count}")
    orphan_count = total_files - covered_count
    lines.append(f"Orphan files: {orphan_count}")
    lines.append("")

    # Safe to skip
    safe_categories = ["entities", "config", "types", "graph_entities",
                       "ui_components", "tests", "styles", "assets",
                       "validations", "routes_infra"]
    safe_total = sum(len(orphan_categories.get(c, [])) for c in safe_categories)

    lines.append(f"Safe to skip ({safe_total} files):")
    for cat in safe_categories:
        files = orphan_categories.get(cat, [])
        if files:
            lines.append(f"  {cat}: {len(files)} files")

    lines.append("")

    # Review needed
    review_categories = ["services", "service_hooks", "utils", "middleware",
                         "hooks", "context", "unknown"]
    review_total = sum(len(orphan_categories.get(c, [])) for c in review_categories)

    lines.append(f"Review needed ({review_total} files):")
    for cat in review_categories:
        files = orphan_categories.get(cat, [])
        if files:
            lines.append(f"  {cat}: {len(files)} files")
            for f in sorted(files, key=lambda x: x.path):
                lines.append(f"    - {f.path} ({f.loc} LOC, {f.repository_name})")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def load_breeze_config(config_path: str = None) -> dict:
    """Load .breeze.json configuration."""
    if config_path is None:
        config_path = BREEZE_CONFIG_FILE

    if not os.path.exists(config_path):
        # Try parent directories
        path = Path.cwd()
        for _ in range(5):
            candidate = path / BREEZE_CONFIG_FILE
            if candidate.exists():
                config_path = str(candidate)
                break
            path = path.parent

    with open(config_path) as f:
        return json.load(f)


def generate_flow_clusters(
    project_uuid: str,
    api_key: str,
    api_base: str = DEFAULT_API_BASE,
    output_dir: str = ".",
    entry_point_filter: Optional[str] = None,
):
    """Main entry point — generates flow cluster documents for a project."""

    client = BreezeAPIClient(api_base, api_key)

    # Step 1: Get all code ontologies for the project
    print(f"Fetching code ontologies for project {project_uuid}...")
    ontologies = client.get_code_ontologies(project_uuid)
    print(f"  Found {len(ontologies)} code ontologies")

    # Step 2: Fetch all files from each ontology
    all_frontend_files = []
    all_backend_files = []

    for ont in ontologies:
        ont_id = ont.get("_id") or ont.get("id")
        ont_name = ont.get("name", "unknown")
        print(f"\nFetching files for ontology: {ont_name} (id={ont_id})...")

        raw_files = client.get_all_files(project_uuid, ont_id, with_children=True)
        print(f"  Fetched {len(raw_files)} files")

        files = [parse_file(f) for f in raw_files]

        # Classify repo type
        if is_frontend_repo(files):
            all_frontend_files.extend(files)
            print(f"  Classified as FRONTEND ({len(files)} files)")
        elif is_backend_repo(files):
            all_backend_files.extend(files)
            print(f"  Classified as BACKEND ({len(files)} files)")
        else:
            # Try both
            if any(re.search(r"controller", f.path, re.IGNORECASE) for f in files):
                all_backend_files.extend(files)
                print(f"  Classified as BACKEND (fallback, {len(files)} files)")
            else:
                all_frontend_files.extend(files)
                print(f"  Classified as FRONTEND (fallback, {len(files)} files)")

    print(f"\nTotal: {len(all_frontend_files)} frontend files, {len(all_backend_files)} backend files")

    # Step 3: Build flow clusters
    print("\nBuilding flow clusters...")
    clusters = build_flow_clusters(
        project_uuid,
        all_frontend_files,
        all_backend_files,
        entry_point_filter=entry_point_filter,
    )
    print(f"  Generated {len(clusters)} flow clusters")

    # Step 4: Build remaining clusters from orphan files grouped by Louvain cluster ID
    all_files = all_frontend_files + all_backend_files
    remaining_clusters = build_orphan_clusters_by_cluster_id(all_files, clusters)

    flow_count = len(clusters)
    remaining_count = len(remaining_clusters)
    remaining_files = sum(
        len(c.frontend_files) + len(c.backend_files) for c in remaining_clusters
    )
    print(f"  + {remaining_count} remaining clusters ({remaining_files} files grouped by Louvain cluster ID)")

    clusters.extend(remaining_clusters)

    # Step 5: Write output files
    os.makedirs(output_dir, exist_ok=True)

    for cluster in clusters:
        safe_name = re.sub(r"[^a-z0-9]+", "-", cluster.name.lower()).strip("-")
        filename = f"{safe_name}-flow-cluster.md"
        filepath = os.path.join(output_dir, filename)

        content = format_flow_cluster(cluster)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        total_files = len(cluster.frontend_files) + len(cluster.backend_files)
        total_loc = sum(f.loc for f in cluster.frontend_files + cluster.backend_files)
        print(f"  Written: {filename} ({total_files} files, {total_loc} LOC, {cluster.flow_type})")

    # Step 6: Write summary report
    flow_covered = len(set(
        f.path for c in clusters for f in c.frontend_files + c.backend_files
        if c.flow_type not in ("REMAINING",)
    ))
    remaining_covered = len(set(
        f.path for c in clusters for f in c.frontend_files + c.backend_files
        if c.flow_type == "REMAINING"
    ))
    orphan_categories = find_orphan_files(all_files, clusters)
    report = format_orphan_report(orphan_categories, len(all_files), flow_covered + remaining_covered)
    report_path = os.path.join(output_dir, "_summary-report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
        f.write(f"\n\nFlow clusters: {flow_count} ({flow_covered} files)")
        f.write(f"\nRemaining clusters (by Louvain ID): {remaining_count} ({remaining_covered} files)")
        f.write(f"\nTotal clusters: {len(clusters)}")
        f.write(f"\nTotal files covered: {flow_covered + remaining_covered} / {len(all_files)}")

    print(f"\n  Flow clusters: {flow_count} ({flow_covered} files)")
    print(f"  Remaining clusters: {remaining_count} ({remaining_covered} files)")
    print(f"  Total files covered: {flow_covered + remaining_covered} / {len(all_files)}")
    print(f"  Summary report: {report_path}")

    print(f"\nDone! {len(clusters)} total cluster files written to {output_dir}/")
    return clusters


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate flow-based cluster documents from BreezeAI code graph"
    )
    parser.add_argument(
        "--project-uuid",
        help="Project UUID (defaults to .breeze.json)",
    )
    parser.add_argument(
        "--api-key",
        help="API key (defaults to .breeze.json)",
    )
    parser.add_argument(
        "--api-base",
        default=DEFAULT_API_BASE,
        help=f"API base URL (default: {DEFAULT_API_BASE})",
    )
    parser.add_argument(
        "--output-dir",
        default="./flow-clusters",
        help="Output directory for cluster files (default: ./flow-clusters)",
    )
    parser.add_argument(
        "--entry-point",
        help="Filter to specific entry point (e.g., 'knowledge-management', 'code-ontology')",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=MAX_TRACE_DEPTH,
        help=f"Maximum call chain depth (default: {MAX_TRACE_DEPTH})",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=MAX_FILES_PER_FLOW,
        help=f"Maximum files per flow cluster (default: {MAX_FILES_PER_FLOW})",
    )

    args = parser.parse_args()

    # Load config
    try:
        config = load_breeze_config()
    except (FileNotFoundError, json.JSONDecodeError):
        config = {}

    project_uuid = args.project_uuid or config.get("projectUuid")
    api_key = args.api_key or config.get("apiKey")

    if not project_uuid:
        print("Error: --project-uuid required (or set in .breeze.json)")
        sys.exit(1)
    if not api_key:
        print("Error: --api-key required (or set in .breeze.json)")
        sys.exit(1)

    generate_flow_clusters(
        project_uuid=project_uuid,
        api_key=api_key,
        api_base=args.api_base,
        output_dir=args.output_dir,
        entry_point_filter=args.entry_point,
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Bulk git-link onboarding for /breeze:onboard-repository.

Connects repos to a Breeze project through the backend's server-side git sync
(POST /code-ontology/generate-from-git), then polls GET /code-ontology until each
ingest is active or errored, retrying errored / stalled ones via POST /sync/:id.

Everything is resumable: state lives in <state-dir>/repos.json and every action is
appended to <state-dir>/log.jsonl. Re-running any subcommand picks up from the state
file — nothing is connected twice (a repo with a codeOntologyId is never re-created).

Stdlib only. Secrets are never printed:
  - Breeze API key: env BREEZE_API_KEY, else `apiKey` in .breeze.json (cwd).
  - Git token: --token-file, else env named by --token-env (default by provider), else `gh auth token` /
    `glab auth token`. Passed to Breeze as gitToken; never logged.

Subcommands
  discover  --provider github|gitlab --org <org|group> [--host H]   list repos into state
  add       --url <https url> [--branch B] [--provider P]           add one repo to state
  tree      [--only name,...]                                       file list per repo (GitHub/GitLab)
  preview                                                           what built-ins + ignore patterns exclude, per repo
  connect   [--max-inflight N]                                      connect selected repos
  status                                                            refresh ingest status
  run       [--max-inflight N] [--interval S] [--max-retries R]     loop: status → retry → connect
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone

IN_FLIGHT = {"started", "node_creation", "relationship_creation", "creating_embeddings", "metadata_addition"}
DEFAULT_TOKEN_ENV = {"github": "GITHUB_TOKEN", "gitlab": "GITLAB_TOKEN",
                     "bitbucket": "BITBUCKET_TOKEN", "azure_devops": "AZURE_DEVOPS_TOKEN"}
STALL_MINUTES = 30  # no stage change for this long → probe with /sync (409 means still alive)


# ---------- state + log ----------

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class State:
    def __init__(self, d):
        self.dir = d
        os.makedirs(os.path.join(d, "ignore"), exist_ok=True)
        os.makedirs(os.path.join(d, "trees"), exist_ok=True)
        self.path = os.path.join(d, "repos.json")
        self.data = json.load(open(self.path)) if os.path.exists(self.path) else {"repos": {}}

    @property
    def repos(self):
        return self.data["repos"]

    def save(self):
        tmp = self.path + ".tmp"
        json.dump(self.data, open(tmp, "w"), indent=1)
        os.replace(tmp, self.path)  # atomic: a crash never leaves a half-written state file

    def log(self, event, repo=None, **kw):
        rec = {"ts": now(), "event": event, **({"repo": repo} if repo else {}), **kw}
        with open(os.path.join(self.dir, "log.jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")


# ---------- http ----------

def http(method, url, headers=None, body=None, timeout=120):
    data = json.dumps(body).encode() if body is not None else None
    h = {"Accept": "application/json", **(headers or {})}
    if data is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {}), dict(r.headers)
    except urllib.error.HTTPError as e:
        txt = e.read().decode(errors="replace")[:500]
        try:
            return e.code, json.loads(txt), dict(e.headers)
        except ValueError:
            return e.code, {"message": txt}, dict(e.headers)


def breeze_cfg(args):
    cfg = json.load(open(".breeze.json")) if os.path.exists(".breeze.json") else {}
    key = os.environ.get("BREEZE_API_KEY") or cfg.get("apiKey")
    if not key:
        sys.exit("No Breeze API key: set BREEZE_API_KEY or apiKey in .breeze.json")
    uuid = args.project or cfg.get("projectUuid")
    if not uuid:
        sys.exit("No project: pass --project <uuid> or set projectUuid in .breeze.json")
    base = (args.api_base or cfg.get("apiBase") or "https://isometric-backend.accionbreeze.com").rstrip("/")
    return base, {"api-key": key}, uuid


TOKEN_FILE = None  # set from --token-file


def git_token(provider, env_name=None):
    if TOKEN_FILE and os.path.exists(os.path.expanduser(TOKEN_FILE)):
        return open(os.path.expanduser(TOKEN_FILE)).read().strip()
    tok = os.environ.get(env_name or DEFAULT_TOKEN_ENV.get(provider, ""), "")
    if tok:
        return tok
    cli = {"github": ["gh", "auth", "token"], "gitlab": ["glab", "auth", "token"]}.get(provider)
    if cli:
        try:
            return subprocess.run(cli, capture_output=True, text=True, timeout=20).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    return ""


def provider_of(url):
    host = urllib.parse.urlparse(url).netloc.lower()
    if "github" in host:
        return "github"
    if "bitbucket" in host:
        return "bitbucket"
    if "dev.azure.com" in host or "visualstudio.com" in host:
        return "azure_devops"
    return "gitlab"


# ---------- discover / add ----------

def discover(args, st):
    prov, tok = args.provider, git_token(args.provider, args.token_env)
    found = []
    if prov == "github":
        api = f"https://{args.host}/api/v3" if args.host and args.host != "github.com" else "https://api.github.com"
        hdr = {"Authorization": f"Bearer {tok}"} if tok else {}
        for kind in ("orgs", "users"):
            page, got = 1, []
            while True:
                s, d, _ = http("GET", f"{api}/{kind}/{args.org}/repos?per_page=100&page={page}&type=all", hdr)
                if s != 200 or not isinstance(d, list):
                    break
                got += d
                if len(d) < 100:
                    break
                page += 1
            if got:
                break
        for r in got:
            found.append({"key": r["full_name"], "name": r["name"], "url": r["html_url"], "branch": r.get("default_branch") or "main",
                          "language": r.get("language"), "sizeKb": r.get("size"), "pushedAt": r.get("pushed_at"),
                          "archived": r.get("archived"), "fork": r.get("fork"), "empty": (r.get("size") or 0) == 0})
    elif prov == "gitlab":
        api = f"https://{args.host or 'gitlab.com'}/api/v4"
        hdr = {"PRIVATE-TOKEN": tok} if tok else {}
        grp = urllib.parse.quote(args.org, safe="")
        page = 1
        while True:
            s, d, _ = http("GET", f"{api}/groups/{grp}/projects?include_subgroups=true&per_page=100&page={page}&statistics=true", hdr)
            if s != 200 or not isinstance(d, list):
                if page == 1:
                    sys.exit(f"GitLab group listing failed: HTTP {s}")
                break
            for r in d:
                stats = r.get("statistics") or {}
                found.append({"key": r["path_with_namespace"], "name": r["path"], "url": r["web_url"],
                              "branch": r.get("default_branch") or "main", "language": None,
                              "sizeKb": (stats.get("repository_size") or 0) // 1024, "pushedAt": r.get("last_activity_at"),
                              "archived": r.get("archived"), "fork": bool(r.get("forked_from_project")),
                              "empty": r.get("empty_repo", False), "gitlabId": r["id"]})
            if len(d) < 100:
                break
            page += 1
    else:
        sys.exit("discover supports github and gitlab; for bitbucket / azure_devops use `add` per repo")
    names = Counter(r["name"] for r in found)
    for r in found:
        if r["key"] in st.repos:
            continue  # keep existing state (selection, ids, status) on re-discover
        r["displayName"] = r["name"] if names[r["name"]] == 1 else r["key"].replace("/", "__")
        st.repos[r["key"]] = {**r, "provider": prov, "selected": None, "status": "discovered"}
    st.save()
    st.log("discover", provider=prov, org=args.org, count=len(found))
    print(f"discovered {len(found)} repos ({len(st.repos)} in state) → {st.path}")


def add(args, st):
    prov = args.provider or provider_of(args.url)
    path = urllib.parse.urlparse(args.url).path.strip("/").removesuffix(".git")
    key = path
    name = path.split("/")[-1]
    if key not in st.repos:
        st.repos[key] = {"key": key, "name": name, "displayName": name, "url": args.url.removesuffix(".git"),
                         "branch": args.branch or "main", "provider": prov, "selected": True, "status": "discovered"}
        st.save()
        st.log("add", key, provider=prov)
    print(f"{key}: in state")


# ---------- tree (for ignore-pattern proposal) ----------

def tree(args, st):
    only = set(args.only.split(",")) if args.only else None
    for key, r in st.repos.items():
        if only and r["name"] not in only and key not in only:
            continue
        if r.get("selected") is False:
            continue
        tok = git_token(r["provider"], args.token_env)
        files, truncated = [], False
        if r["provider"] == "github":
            api = "https://api.github.com"
            hdr = {"Authorization": f"Bearer {tok}"} if tok else {}
            s, d, _ = http("GET", f"{api}/repos/{key}/git/trees/{urllib.parse.quote(r['branch'])}?recursive=1", hdr)
            if s == 200:
                files = [t["path"] for t in d.get("tree", []) if t.get("type") == "blob"]
                truncated = bool(d.get("truncated"))
        elif r["provider"] == "gitlab":
            host = urllib.parse.urlparse(r["url"]).netloc
            hdr = {"PRIVATE-TOKEN": tok} if tok else {}
            pid = r.get("gitlabId") or urllib.parse.quote(key, safe="")
            page = 1
            while page <= 200:
                s, d, _ = http("GET", f"https://{host}/api/v4/projects/{pid}/repository/tree?recursive=true&per_page=100"
                                      f"&page={page}&ref={urllib.parse.quote(r['branch'])}", hdr)
                if s != 200 or not isinstance(d, list):
                    break
                files += [t["path"] for t in d if t.get("type") == "blob"]
                if len(d) < 100:
                    break
                page += 1
            truncated = page > 200
        else:
            print(f"{key}: tree not supported for {r['provider']} — propose ignores from stack defaults")
            continue
        out = os.path.join(st.dir, "trees", key.replace("/", "__") + ".txt")
        open(out, "w").write("\n".join(files))
        ext = Counter(os.path.splitext(f)[1].lower() or "(none)" for f in files)
        top = Counter(f.split("/")[0] if "/" in f else "(root)" for f in files)
        r["tree"] = {"files": len(files), "truncated": truncated, "path": out,
                     "topExt": ext.most_common(8), "topDirs": top.most_common(10)}
        st.save()
        st.log("tree", key, files=len(files), truncated=truncated)
        print(f"{key}: {len(files)} files{' (TRUNCATED)' if truncated else ''} → {out}")


# ---------- preview (gitignore semantics) ----------

# COG's built-in defaults (breezeai_cog/core/default_ignores.txt) — kept in sync by hand.
COG_DEFAULTS = """.git/ .svn/ .hg/ node_modules/ vendor/ bower_components/ jspm_packages/ package-lock.json
npm-shrinkwrap.json yarn.lock pnpm-lock.yaml bun.lockb __pycache__/ *.pyc *.pyo .venv/ venv/ .tox/ .mypy_cache/
.pytest_cache/ .ruff_cache/ *.egg-info/ dist/ build/ out/ target/ bin/ obj/ .next/ .nuxt/ .svelte-kit/ *.min.js
*.min.css .cache/ .parcel-cache/ .gradle/ .idea/ .vscode/ .env .env.* *.pem *.key id_rsa* *.log logs/ tmp/ temp/
.cog/ *.tfstate *.tfstate.backup .terraform.lock.hcl test/ tests/ __tests__/ *.test.* *.spec.* test_*.py
*_test.py *_test.go""".split()
SUPPORTED_EXT = {".cs", ".vb", ".java", ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
                 ".html", ".htm", ".cshtml", ".razor", ".aspx", ".ascx", ".master", ".vue"}


def gi_regex(pat):
    """gitignore pattern → regex over a repo-relative path (no negation; COG doesn't support it)."""
    dir_only = pat.endswith("/")
    pat = pat.rstrip("/")
    anchored = pat.startswith("/") or "/" in pat
    pat = pat.lstrip("/")
    i, out = 0, ""
    while i < len(pat):
        if pat.startswith("**/", i):
            out += "(?:.*/)?"
            i += 3
        elif pat.startswith("/**", i) and i + 3 == len(pat):
            out += "/.*"
            i += 3
        elif pat[i] == "*":
            out += "[^/]*"
            i += 1
        elif pat[i] == "?":
            out += "[^/]"
            i += 1
        else:
            out += re.escape(pat[i])
            i += 1
    head = "^" if anchored else "^(?:.*/)?"
    tail = "/" if dir_only else "(?:/|$)"
    return re.compile(head + out + tail)


def preview(args, st):
    for key, r in st.repos.items():
        if r.get("selected") is False or not r.get("tree"):
            continue
        files = [f for f in open(r["tree"]["path"]).read().split("\n") if f]
        own = (ignore_text(st, r) or "").splitlines()
        own = [l.strip() for l in own if l.strip() and not l.strip().startswith("#")]
        builtin = [gi_regex(p) for p in COG_DEFAULTS]
        mine = [(p, gi_regex(p)) for p in own]
        kept, by_builtin, by_mine, unsupported = [], 0, Counter(), 0
        for f in files:
            if os.path.splitext(f)[1].lower() not in SUPPORTED_EXT:
                unsupported += 1
                continue
            if any(rx.search(f) for rx in builtin):
                by_builtin += 1
                continue
            hit = next((p for p, rx in mine if rx.search(f)), None)
            if hit:
                by_mine[hit] += 1
                continue
            kept.append(f)
        r["preview"] = {"files": len(files), "notParsed": unsupported, "builtinExcluded": by_builtin,
                        "patternExcluded": sum(by_mine.values()), "kept": len(kept)}
        st.save()
        print(f"{key}: {len(files)} files · not parsed (type) {unsupported} · built-in excluded {by_builtin} · "
              f"your patterns excluded {sum(by_mine.values())} · kept {len(kept)}")
        for p, n in by_mine.most_common(10):
            print(f"    {n:>5}  {p}")
        unused = [p for p in own if p not in by_mine]
        if unused:
            print(f"    unused patterns: {', '.join(unused)}")


# ---------- connect / status / retry ----------

def ignore_text(st, r):
    for fn in (r["key"].replace("/", "__"), "_default"):
        p = os.path.join(st.dir, "ignore", fn + ".repoignore")
        if os.path.exists(p):
            return open(p).read().strip() or None
    return None


def refresh(st, base, hdr, uuid):
    """GET /code-ontology for the project; map rows back onto state by codeOntologyId."""
    rows, page = [], 1
    sel = "_id,name,status,fileGraphStatus,statusMessage,failedStep,erroredAt,fileCount,classCount,functionCount,updatedAt,repoUrl"
    while True:
        q = urllib.parse.urlencode({"filters[projectUuid][$eq]": uuid, "selectFields": sel, "limit": 100, "page": page})
        s, d, _ = http("GET", f"{base}/code-ontology?{q}", hdr)
        if s != 200:
            st.log("status_error", http=s, message=str(d)[:200])
            return None
        rows += d.get("data", [])
        if len(d.get("data", [])) < 100:
            break
        page += 1
    by_id = {row["_id"]: row for row in rows}
    name_counts = Counter(row.get("name") for row in rows)
    by_name = {row.get("name"): row for row in rows if name_counts[row.get("name")] == 1}
    for key, r in st.repos.items():
        if not r.get("codeOntologyId") and r.get("status") == "uploaded" and r.get("displayName") in by_name:
            # Local uploads don't return an id: adopt the project's only code ontology with this name.
            r["codeOntologyId"] = by_name[r["displayName"]]["_id"]
            st.log("matched_by_name", key, codeOntologyId=r["codeOntologyId"])
        row = by_id.get(r.get("codeOntologyId"))
        if not row:
            continue
        fg = row.get("fileGraphStatus")
        new = "indexed" if fg == "active" else "error" if fg == "error" else "ingesting" if fg in IN_FLIGHT else r["status"]
        if new != r["status"] or fg != r.get("fileGraphStatus"):
            st.log("status", key, status=new, fileGraphStatus=fg, failedStep=row.get("failedStep"))
        r.update(status=new, fileGraphStatus=fg, statusMessage=row.get("statusMessage"), failedStep=row.get("failedStep"),
                 fileCount=row.get("fileCount"), classCount=row.get("classCount"), functionCount=row.get("functionCount"),
                 serverUpdatedAt=row.get("updatedAt"), checkedAt=now())
    st.save()
    return rows


def connect_one(st, base, hdr, uuid, key, r, token_env):
    tok = git_token(r["provider"], token_env)
    body = {"projectUuid": uuid, "name": r["displayName"], "repoUrl": r["url"], "gitBranch": r["branch"],
            "gitProvider": r["provider"]}
    if tok:
        body["gitToken"] = tok
    ign = ignore_text(st, r)
    if ign:
        body["ignorePatterns"] = ign
    s, d, _ = http("POST", f"{base}/code-ontology/generate-from-git", hdr, body)
    if s in (200, 201) and d.get("data", {}).get("_id"):
        r.update(status="ingesting", codeOntologyId=d["data"]["_id"], connectedAt=now(), attempts=0)
        st.log("connected", key, codeOntologyId=r["codeOntologyId"], ignorePatterns=bool(ign))
    else:
        r.update(status="connect_failed", lastError=f"HTTP {s}: {str(d.get('message', d))[:200]}")
        st.log("connect_failed", key, http=s, message=r["lastError"])
    st.save()


def retry_one(st, base, hdr, key, r):
    """Re-sync an errored / suspected-stalled ingest. 409 from /sync means the ingest is alive."""
    cid = r["codeOntologyId"]
    s, d, _ = http("GET", f"{base}/code-ontology/check-update/{cid}", hdr)
    if s != 200:
        st.log("retry_check_failed", key, http=s)
        return
    incoming = d.get("latestCommitId") or d.get("currentCommitId")
    s, d, _ = http("POST", f"{base}/code-ontology/sync/{cid}", hdr, {"incomingCommitId": incoming})
    if s == 409:
        r["stallProbeAt"] = now()
        st.log("still_running", key)  # backend heartbeat is fresh — not stalled
    elif s in (200, 201):
        r["attempts"] = r.get("attempts", 0) + 1
        r.update(status="ingesting", retriedAt=now())
        st.log("retried", key, attempt=r["attempts"], incomingCommitId=incoming)
    else:
        st.log("retry_failed", key, http=s, message=str(d)[:200])
    st.save()


def stalled(r):
    ts = r.get("serverUpdatedAt")
    if r["status"] != "ingesting" or not ts:
        return False
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds() / 60
    last_probe = r.get("stallProbeAt")
    if last_probe:
        since = (datetime.now(timezone.utc) - datetime.fromisoformat(last_probe)).total_seconds() / 60
        if since < STALL_MINUTES:
            return False
    return age > STALL_MINUTES


def summary(st):
    c = Counter(r["status"] for r in st.repos.values() if r.get("selected"))
    return ", ".join(f"{k}={v}" for k, v in sorted(c.items())) or "nothing selected"


def cycle(args, st, base, hdr, uuid):
    refresh(st, base, hdr, uuid)
    for key, r in st.repos.items():
        if not r.get("selected") or not r.get("codeOntologyId") or not r.get("url"):
            continue  # local uploads (no url) can't be re-synced from git
        if (r["status"] == "error" or stalled(r)) and r.get("attempts", 0) < args.max_retries:
            retry_one(st, base, hdr, key, r)
    inflight = sum(1 for r in st.repos.values() if r.get("selected") and r["status"] == "ingesting")
    for key, r in st.repos.items():
        if inflight >= args.max_inflight:
            break
        if r.get("selected") and r["status"] in ("discovered", "planned") and not r.get("codeOntologyId"):
            connect_one(st, base, hdr, uuid, key, r, args.token_env)
            if r["status"] == "ingesting":
                inflight += 1
    print(f"[{now()}] {summary(st)}")


def done(st, max_retries):
    for r in st.repos.values():
        if not r.get("selected"):
            continue
        if r["status"] in ("discovered", "planned", "ingesting"):
            return False
        if r["status"] == "error" and r.get("url") and r.get("attempts", 0) < max_retries:
            return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["discover", "add", "tree", "preview", "connect", "status", "run"])
    ap.add_argument("--state-dir", default=".breeze/onboarding")
    ap.add_argument("--project")
    ap.add_argument("--api-base")
    ap.add_argument("--provider", choices=["github", "gitlab", "bitbucket", "azure_devops"])
    ap.add_argument("--org")
    ap.add_argument("--host")
    ap.add_argument("--url")
    ap.add_argument("--branch")
    ap.add_argument("--only")
    ap.add_argument("--token-env")
    ap.add_argument("--token-file", help="file holding the git token (chmod 600); never printed")
    ap.add_argument("--max-inflight", type=int, default=5)
    ap.add_argument("--max-retries", type=int, default=2)
    ap.add_argument("--interval", type=int, default=60)
    args = ap.parse_args()
    global TOKEN_FILE
    TOKEN_FILE = args.token_file
    st = State(args.state_dir)
    if args.cmd == "discover":
        return discover(args, st)
    if args.cmd == "add":
        return add(args, st)
    if args.cmd == "tree":
        return tree(args, st)
    if args.cmd == "preview":
        return preview(args, st)
    base, hdr, uuid = breeze_cfg(args)
    if args.cmd == "status":
        refresh(st, base, hdr, uuid)
        print(summary(st))
        for key, r in st.repos.items():
            if r.get("selected") and r["status"] in ("error", "connect_failed"):
                print(f"  {key}: {r['status']} {r.get('failedStep') or ''} {r.get('statusMessage') or r.get('lastError') or ''}")
        return
    if args.cmd == "connect":
        args.max_retries = 0
        return cycle(args, st, base, hdr, uuid)
    st.log("run_start", maxInflight=args.max_inflight)
    while True:
        cycle(args, st, base, hdr, uuid)
        if done(st, args.max_retries):
            st.log("run_done", summary=summary(st))
            print("done:", summary(st))
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()

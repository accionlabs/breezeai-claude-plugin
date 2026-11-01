#!/usr/bin/env python3
"""P5 join for /breeze:onboard-project: match every human REST call to a System handler.

Reads the LIVE functional graph (Api nodes over REST), never payload files — the
upsert dedups apis, so payloads and graph differ.

  python3 join.py [--project <uuid>] [--out .breeze/join_report.json]
                  [--verbless "/App/Home/SaveSnapshot,..."]   MVC actions with no verb attribute (match any method)

Rules
- key = METHOD + path; path lower-cased, query string and trailing "/" dropped, {param} → :p.
- A human call whose path matches a System handler but whose method differs is a match only if
  that path is listed in --verbless (an MVC action without [HttpGet]/[HttpPost] accepts any verb).
- Results: matched · verb-agnostic · method-mismatch · NO HANDLER (the code has nothing at that
  path — a finding for the customer, not a graph fix) · external (absolute URL to another host).
- System routes nobody calls are listed too (page GETs are expected there).

Credentials: env BREEZE_API_KEY or apiKey in .breeze.json (cwd). Never printed.
"""
import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from collections import Counter


def cfg(project):
    c = json.load(open(".breeze.json")) if os.path.exists(".breeze.json") else {}
    key = os.environ.get("BREEZE_API_KEY") or c.get("apiKey")
    if not key:
        raise SystemExit("no API key (BREEZE_API_KEY or .breeze.json apiKey)")
    return (c.get("apiBase") or "https://isometric-backend.accionbreeze.com").rstrip("/"), {"api-key": key}, project or c.get("projectUuid")


def fetch(base, hdr, uuid, label):
    rows, page = [], 1
    while True:
        q = urllib.parse.urlencode({"page": page, "limit": 100})
        r = urllib.request.Request(f"{base}/functional-graph/{uuid}/{label}?{q}", headers=hdr)
        data = json.loads(urllib.request.urlopen(r, timeout=300).read()).get("data", [])
        rows += data
        if len(data) < 100:
            return rows
        page += 1


def norm(url):
    u = re.sub(r"\?.*", "", url or "").rstrip("/").lower()
    return re.sub(r"\{[^}]+\}", ":p", u)


def persona(api):
    m = re.match(r"Persona: (.*)", api.get("embedText") or "")
    return m.group(1).strip() if m else "?"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project")
    ap.add_argument("--out", default=".breeze/join_report.json")
    ap.add_argument("--verbless", default="")
    o = ap.parse_args()
    base, hdr, uuid = cfg(o.project)
    verbless = {norm(v) for v in o.verbless.split(",") if v}
    apis = [a for a in fetch(base, hdr, uuid, "Api") if (a.get("type") or "").upper() == "REST" and a.get("url")]
    system = [a for a in apis if persona(a) in ("System", "External System")]
    human = [a for a in apis if persona(a) not in ("System", "External System")]
    handlers = {}
    for a in system:
        handlers.setdefault(norm(a["url"]), set()).add((a.get("method") or "GET").upper())
    rows = []
    for a in human:
        url, m = a["url"], (a.get("method") or "GET").upper()
        if re.match(r"(?i)^(https?:)?//", url):
            res = "external"
        elif not url.startswith("/"):
            res = "relative-url"  # fix the generator: urls must be absolute paths (/<app>/<controller>/<action>)
        else:
            p = norm(url)
            if p not in handlers:
                res = "NO HANDLER"
            elif m in handlers[p]:
                res = "matched"
            elif p in verbless:
                res = "verb-agnostic"
            else:
                res = f"method-mismatch (System has {','.join(sorted(handlers[p]))})"
        rows.append({"result": res, "persona": persona(a), "method": m, "url": url, "apiId": a["id"]})
    called = {norm(r["url"]) for r in rows}
    uncalled = sorted(f"{','.join(sorted(ms))} {p}" for p, ms in handlers.items() if p not in called)
    summary = Counter(r["result"].split(" (")[0] for r in rows)
    report = {"humanRestCalls": len(rows), "summary": dict(summary), "calls": rows, "systemRoutesNotCalledByHumans": uncalled}
    os.makedirs(os.path.dirname(o.out) or ".", exist_ok=True)
    json.dump(report, open(o.out, "w"), indent=1)
    print(json.dumps(report["summary"]))
    for r in rows:
        if r["result"] != "matched":
            print(f"  {r['result']:<34} {r['method']:<6} {r['url']}  [{r['persona']}]")
    print(f"report → {o.out}")


if __name__ == "__main__":
    main()

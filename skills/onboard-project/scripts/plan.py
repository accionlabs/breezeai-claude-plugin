#!/usr/bin/env python3
"""Plan helper for /breeze:onboard-project — the single writer of .breeze/plan.json.

Every change is written atomically (temp file + rename) and appended to
.breeze/plan.log.jsonl, so a crashed or stalled session can always resume.

  init   --project <uuid> --name <name> [--mode interactive|autonomous]
  source --key <key> [--url URL] [--path PATH] [--branch B]
  unit   --id ID --type TYPE --root PATH [--skill s1,s2] [--source KEY] [--fold a,b] [--personas a,b] [--out-of-scope]
  group  --id ID --skill SKILL --units u1,u2 [--root PATH] [--out DIR]   run group = one skill run over several units
  add    <step-id> <phase> [deps,..]
  set    <step-id> pending|running|done|failed|skipped|blocked [detail...]
  gate   <gate-id> <decision> [detail...]       records mode + decision (G1..G7)
  note   <text...>
  status                                          steps, next runnable step, failed steps, gates
  next                                            print the first runnable step id (exit 1 if none)
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

PLAN = ".breeze/plan.json"
LOG = ".breeze/plan.log.jsonl"
PHASES = ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8"]
DEPS = {"P1": ["P0"], "P2": ["P1"], "P3": ["P2"], "P4": ["P3"], "P5": ["P4"], "P6": ["P2"], "P7": ["P5"], "P8": ["P5", "P6", "P7"]}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load():
    if not os.path.exists(PLAN):
        sys.exit("no plan: run `plan.py init` first")
    return json.load(open(PLAN))


def save(plan):
    plan["updatedAt"] = now()
    os.makedirs(os.path.dirname(PLAN), exist_ok=True)
    json.dump(plan, open(PLAN + ".tmp", "w"), indent=1)
    os.replace(PLAN + ".tmp", PLAN)


def log(**kw):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps({"ts": now(), **kw}) + "\n")


def step(plan, sid):
    for s in plan["steps"]:
        if s["id"] == sid:
            return s
    sys.exit(f"unknown step {sid}")


def runnable(plan):
    done = {s["id"] for s in plan["steps"] if s["status"] in ("done", "skipped")}
    for s in plan["steps"]:
        if s["status"] in ("pending", "running", "failed") and all(d in done for d in s.get("dependsOn", [])):
            yield s


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    cmd, rest = a[0], a[1:]
    if cmd == "init":
        ap = argparse.ArgumentParser()
        ap.add_argument("--project", required=True)
        ap.add_argument("--name", default="")
        ap.add_argument("--mode", default="interactive", choices=["interactive", "autonomous"])
        o = ap.parse_args(rest)
        if os.path.exists(PLAN):
            sys.exit("plan exists — use status / next (delete .breeze/plan.json to start over)")
        plan = {"version": 1, "projectUuid": o.project, "projectName": o.name, "mode": o.mode,
                "createdAt": now(), "updatedAt": now(), "scope": {"capabilities": ["all"], "excludeUnits": []},
                "sources": [], "units": [], "runGroups": [], "personas": {"status": "pending", "list": []},
                "designExclusions": [], "gates": [], "checks": [],
                "steps": [{"id": p, "phase": p, "dependsOn": DEPS.get(p, []), "status": "pending", "attempts": 0} for p in PHASES]}
        save(plan)
        log(step="plan", to="created", mode=o.mode)
        print(f"plan created ({o.mode})")
        return
    plan = load()
    if cmd == "source":
        ap = argparse.ArgumentParser()
        for f in ("--key", "--url", "--path", "--branch"):
            ap.add_argument(f)
        o = ap.parse_args(rest)
        plan["sources"] = [s for s in plan["sources"] if s["key"] != o.key] + [{"key": o.key, "url": o.url, "path": o.path, "branch": o.branch}]
        save(plan)
        log(note=f"source {o.key}")
    elif cmd == "unit":
        ap = argparse.ArgumentParser()
        for f in ("--id", "--type", "--root", "--skill", "--source", "--fold", "--personas"):
            ap.add_argument(f)
        ap.add_argument("--out-of-scope", action="store_true")
        o = ap.parse_args(rest)
        split = lambda v: [x for x in (v or "").split(",") if x]
        u = {"id": o.id, "type": o.type, "root": o.root, "skill": split(o.skill), "source": o.source,
             "foldIn": split(o.fold), "personas": split(o.personas), "inScope": not o.out_of_scope}
        plan["units"] = [x for x in plan["units"] if x["id"] != o.id] + [u]
        save(plan)
        log(note=f"unit {o.id} ({o.type})")
    elif cmd == "group":
        ap = argparse.ArgumentParser()
        for f in ("--id", "--skill", "--units", "--root", "--out"):
            ap.add_argument(f)
        o = ap.parse_args(rest)
        g = {"id": o.id, "skill": o.skill, "units": o.units.split(","), "root": o.root,
             "outputDir": o.out or f".breeze/out/{o.id}"}
        plan["runGroups"] = [x for x in plan["runGroups"] if x["id"] != o.id] + [g]
        sid = f"P4:{o.id}" if "functional" in (o.skill or "") else f"P7:{o.id}"
        if not any(s["id"] == sid for s in plan["steps"]):
            ph = sid.split(":")[0]
            plan["steps"].append({"id": sid, "phase": ph, "dependsOn": DEPS[ph], "status": "pending", "attempts": 0, "group": o.id})
        save(plan)
        log(note=f"run group {o.id} → {o.skill} over {len(g['units'])} units")
    elif cmd == "add":
        sid, ph = rest[0], rest[1]
        deps = rest[2].split(",") if len(rest) > 2 else DEPS.get(ph, [])
        if not any(s["id"] == sid for s in plan["steps"]):
            plan["steps"].append({"id": sid, "phase": ph, "dependsOn": deps, "status": "pending", "attempts": 0})
            save(plan)
            log(step=sid, to="added")
    elif cmd == "set":
        sid, st, det = rest[0], rest[1], " ".join(rest[2:])
        s = step(plan, sid)
        old = s["status"]
        s["status"] = st
        if st == "running":
            s["startedAt"] = now()
            s["attempts"] = s.get("attempts", 0) + 1
        if st in ("done", "failed", "skipped"):
            s["finishedAt"] = now()
        if det:
            s["result" if st == "done" else "error" if st == "failed" else "detail"] = det
        # a phase is done when all its sub-steps are done
        ph = s["phase"]
        subs = [x for x in plan["steps"] if x["phase"] == ph and x["id"] != ph]
        if subs and all(x["status"] in ("done", "skipped") for x in subs):
            parent = step(plan, ph)
            if parent["status"] != "done":
                parent["status"], parent["finishedAt"] = "done", now()
                log(step=ph, to="done", detail="all sub-steps done")
        save(plan)
        log(step=sid, **{"from": old, "to": st, "detail": det})
    elif cmd == "gate":
        gid, dec, det = rest[0], rest[1], " ".join(rest[2:])
        plan["gates"].append({"gate": gid, "mode": plan.get("mode"), "decision": dec, "detail": det, "ts": now()})
        save(plan)
        log(gate=gid, mode=plan.get("mode"), decision=dec, detail=det)
    elif cmd == "note":
        log(note=" ".join(rest))
    elif cmd == "next":
        for s in runnable(plan):
            print(s["id"])
            return
        sys.exit(1)
    elif cmd == "status":
        print(f"{plan.get('projectName')} ({plan['projectUuid']}) · mode {plan.get('mode')} · updated {plan['updatedAt']}")
        for s in plan["steps"]:
            info = s.get("result") or s.get("error") or s.get("detail") or ""
            print(f"  {s['id']:<26} {s['status']:<8} {info}"[:170])
        nxt = next(runnable(plan), None)
        print("next:", nxt["id"] if nxt else "— (nothing runnable)")
        for g in plan["gates"][-7:]:
            print(f"  gate {g['gate']}: {g['decision']} ({g['mode']}) {g['detail']}"[:170])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()

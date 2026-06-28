#!/usr/bin/env python3
"""Agent API 集成测试"""

import json
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:8080"
passed = 0
failed = 0


def req(method, path, body=None, token=None):
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(r)
        body_data = resp.read()
        return resp.status, json.loads(body_data) if body_data else {}
    except urllib.error.HTTPError as e:
        body_data = e.read()
        return e.code, json.loads(body_data) if body_data else {"error": str(e)}
    except urllib.error.URLError as e:
        return 0, {"error": str(e.reason)}


def check(name, status, expected, body=None, key=None, val=None):
    global passed, failed
    ok = True
    if status == 0:
        ok = False
        detail = f"CONNECTION REFUSED (SpringBoot running?)"
    elif isinstance(expected, list):
        ok = status in expected
        detail = f"status={status} expected in {expected}"
    else:
        ok = status == expected
        detail = f"status={status} expected={expected}"
    if ok and key and body:
        ok = body.get(key) == val
        detail += f"  {key}={body.get(key)}"
    elif key and not body:
        ok = False
        detail += "  (body is None)"
    tag = "PASS" if ok else "FAIL"
    if ok:
        passed += 1
    else:
        failed += 1
    print(f"  [{tag}] {name} ({detail})")


# ── Login ──
print("=== Login ===")
status, data = req("POST", "/api/auth/login", {"username": "admin", "password": "Admin@123456"})
token = data.get("token", "")
check("Login", status, 200)

# ── 1. List ──
print("\n=== 1. GET /api/agents ===")
status, data = req("GET", "/api/agents", token=token)
check("List agents", status, 200)
agents = data if isinstance(data, list) else []
print(f"  count={len(agents)}")

# ── 2. Create ──
print("\n=== 2. POST /api/agents ===")
new_agent = {
    "name": "test-agent-py",
    "display_name": "Test Agent Python",
    "system_prompt": "You are a test agent.",
    "icon": "🧪",
    "agent_type": "assistant",
    "tools": ["search", "python"],
    "collaboration_strategy": "sequential",
    "priority": 5,
    "tags": ["test", "api"],
}
status, created = req("POST", "/api/agents", body=new_agent, token=token)
check("Create agent", status, [200, 201])
agent_id = created.get("id", "")
print(f"  id={agent_id}")

# ── 3. Get ──
print(f"\n=== 3. GET /api/agents/{agent_id} ===")
status, data = req("GET", f"/api/agents/{agent_id}", token=token)
check("Get agent by id", status, 200, key="name", val="test-agent-py")

# ── 4. Update ──
print(f"\n=== 4. PUT /api/agents/{agent_id} ===")
update = {
    "name": "test-agent-py",
    "display_name": "Test Agent Updated",
    "system_prompt": "Updated prompt.",
    "icon": "🧪",
    "tools": ["search"],
}
status, data = req("PUT", f"/api/agents/{agent_id}", body=update, token=token)
check("Update agent", status, 200, key="display_name", val="Test Agent Updated")

# ── 5. Disable ──
print(f"\n=== 5. POST /api/agents/{agent_id}/disable ===")
status, data = req("POST", f"/api/agents/{agent_id}/disable", token=token)
check("Disable agent", status, 200, key="enabled", val=False)

# ── 6. Enable ──
print(f"\n=== 6. POST /api/agents/{agent_id}/enable ===")
status, data = req("POST", f"/api/agents/{agent_id}/enable", token=token)
check("Enable agent", status, 200, key="enabled", val=True)

# ── 7. Clone ──
print(f"\n=== 7. POST /api/agents/{agent_id}/clone ===")
status, cloned = req("POST", f"/api/agents/{agent_id}/clone", token=token)
check("Clone agent", status, 200)
clone_id = cloned.get("id", "")
check("Clone new id", status, 200, body=cloned, key="id", val=clone_id)

# ── 8. Delete ──
for aid, label in [(clone_id, "cloned"), (agent_id, "original")]:
    if not aid:
        print(f"\n  [SKIP] Delete {label} — no id")
        continue
    print(f"\n=== 8. DELETE /api/agents/{aid} ({label}) ===")
    status, _ = req("DELETE", f"/api/agents/{aid}", token=token)
    check(f"Delete {label}", status, [200, 204])

print(f"\n{'='*50}")
print(f"Results: {passed} passed, {failed} failed, {passed+failed} total")
if failed:
    sys.exit(1)

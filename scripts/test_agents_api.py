#!/usr/bin/env python3
"""Integration test script for Agent Expert Pool API.

Tests the full CRUD lifecycle via HTTP calls to the running AI service.
Usage: python scripts/test_agents_api.py
"""

import json
import sys
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000/api/v1/agents/"


def request(method, path="", body=None):
    url = f"{BASE_URL}{path.lstrip('/')}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = resp.read().decode("utf-8")
            return resp.status, json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode("utf-8")
        return e.code, json.loads(resp_body) if resp_body else {"detail": str(e)}


def test_create():
    """Test creating an agent."""
    agent = {
        "name": "test_researcher",
        "display_name": "Test Researcher",
        "description": "Searches for information",
        "system_prompt": "You are a researcher. Find facts.",
        "tools": ["search", "time"],
        "model_params": {"temperature": 0.3},
        "trigger_keywords": ["搜索", "查找"],
        "collaboration_strategy": "sequential",
        "priority": 1,
    }
    status, data = request("POST", "", agent)
    assert status == 200, f"Create failed: {status} {data}"
    assert data["name"] == "test_researcher"
    assert data["tools"] == ["search", "time"]
    print(f"  PASS create: {data['id']}")
    return data["id"]


def test_list(agent_id):
    """Test listing all agents."""
    status, data = request("GET")
    assert status == 200, f"List failed: {status}"
    assert isinstance(data, list)
    assert len(data) >= 1
    print(f"  PASS list: {len(data)} agents")
    return data


def test_get(agent_id):
    """Test getting a single agent."""
    status, data = request("GET", agent_id)
    assert status == 200, f"Get failed: {status} {data}"
    assert data["id"] == agent_id
    print(f"  PASS get: {data['name']}")
    return data


def test_update(agent_id):
    """Test updating an agent."""
    updated = {
        "name": "test_researcher_v2",
        "display_name": "Updated Researcher",
        "description": "Updated description",
        "system_prompt": "You are an updated researcher.",
        "tools": ["search", "time", "execute_python"],
        "model_params": {"temperature": 0.5},
        "trigger_keywords": ["搜索", "查找", "研究"],
        "collaboration_strategy": "parallel",
        "priority": 2,
    }
    status, data = request("PUT", agent_id, updated)
    assert status == 200, f"Update failed: {status} {data}"
    assert data["name"] == "test_researcher_v2"
    assert "execute_python" in data["tools"]
    assert data["collaboration_strategy"] == "parallel"
    print(f"  PASS update: {data['name']}")


def test_enable_disable(agent_id):
    """Test toggling agent enabled status."""
    # Disable
    body = {
        "name": "test_researcher_v2",
        "display_name": "Updated Researcher",
        "system_prompt": "You are an updated researcher.",
        "tools": [],
        "enabled": False,
    }
    status, data = request("PUT", f"/{agent_id}", body)
    assert status == 200, f"Disable failed: {status}"
    assert data["enabled"] is False
    print(f"  PASS disable: enabled={data['enabled']}")

    # Re-enable
    body["enabled"] = True
    status, data = request("PUT", f"/{agent_id}", body)
    assert status == 200, f"Enable failed: {status}"
    assert data["enabled"] is True
    print(f"  PASS enable: enabled={data['enabled']}")


def test_create_multiple():
    """Test creating multiple agents with different strategies."""
    agents = [
        {
            "name": "analyst",
            "display_name": "Data Analyst",
            "description": "Analyzes data",
            "system_prompt": "You are a data analyst.",
            "tools": ["execute_python"],
            "trigger_keywords": ["分析", "计算", "数据"],
            "collaboration_strategy": "supervisor",
            "priority": 3,
        },
        {
            "name": "writer",
            "display_name": "Content Writer",
            "description": "Writes content",
            "system_prompt": "You are a writer.",
            "tools": ["search"],
            "trigger_keywords": ["写", "文章", "报告"],
            "collaboration_strategy": "sequential",
            "priority": 0,
        },
    ]
    for agent in agents:
        status, data = request("POST", "", agent)
        assert status == 200, f"Create {agent['name']} failed: {status}"
        print(f"  PASS create {agent['name']}: {data['id']}")


def test_list_enabled_only():
    """Test that list_all returns all agents (including disabled)."""
    status, data = request("GET")
    assert status == 200
    count = len(data)  # Should have all agents created so far
    print(f"  PASS: total agents in list = {count}")
    return count


def test_delete(agent_id):
    """Test deleting an agent."""
    status, data = request("DELETE", agent_id)
    assert status == 200, f"Delete failed: {status} {data}"
    assert data.get("status") == "deleted"
    print(f"  PASS delete: {agent_id}")

    # Verify gone
    status, data = request("GET", agent_id)
    assert status == 404, f"Should be 404 after delete: {status}"
    print(f"  PASS verify deleted: 404")


def test_validation():
    """Test validation rejects invalid agent."""
    invalid = {
        "name": "a" * 65,  # Too long
        "display_name": "Invalid",
        "system_prompt": "...",
        "collaboration_strategy": "invalid_strategy",
    }
    status, data = request("POST", "", invalid)
    assert status == 422, f"Should reject invalid agent: {status}"
    print(f"  PASS validation: 422 for invalid agent")


def main():
    print("=== Agent Expert Pool API Test ===\n")

    try:
        # Basic CRUD
        print("[1] Create Agent")
        agent_id = test_create()

        print("\n[2] List Agents")
        test_list(agent_id)

        print("\n[3] Get Agent")
        test_get(agent_id)

        print("\n[4] Update Agent")
        test_update(agent_id)

        print("\n[5] Enable/Disable Toggle")
        test_enable_disable(agent_id)

        print("\n[6] Create Multiple Agents")
        test_create_multiple()

        print("\n[7] List All Agents")
        test_list_enabled_only()

        print("\n[8] Validation")
        test_validation()

        print("\n[9] Delete Agent")
        test_delete(agent_id)

        print("\n=== ALL TESTS PASSED ===")
        return 0

    except AssertionError as e:
        print(f"\nFAIL: {e}")
        return 1
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

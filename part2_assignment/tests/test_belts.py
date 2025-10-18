import json
import subprocess
import sys
import os

# Use sys.executable to ensure we use the same python interpreter
PYTHON_CMD = sys.executable
BELTS_SCRIPT = os.path.join("belts", "main.py")

def run_belts_solver(input_data):
    """Helper function to run the belts solver as a subprocess."""
    process = subprocess.run(
        [PYTHON_CMD, BELTS_SCRIPT],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        check=False  # We will check the return code manually
    )
    if process.returncode != 0:
        raise RuntimeError(f"Belts solver failed with error:\n{process.stderr}")
    return json.loads(process.stdout)

def test_simple_feasible_flow():
    """A basic feasible flow problem."""
    input_data = {
        "sources": {"s1": 100},
        "sink": "t1",
        "edges": [
            {"from": "s1", "to": "a", "lo": 0, "hi": 100},
            {"from": "a", "to": "t1", "lo": 0, "hi": 100}
        ],
        "node_caps": {}
    }
    output = run_belts_solver(input_data)
    assert output["status"] == "ok"
    assert abs(output["max_flow_per_min"] - 100) < 1e-9

def test_infeasible_due_to_cut():
    """An infeasible problem where the max flow is less than the supply."""
    input_data = {
        "sources": {"s1": 100},
        "sink": "t1",
        "edges": [
            {"from": "s1", "to": "a", "lo": 0, "hi": 100},
            {"from": "a", "to": "t1", "lo": 0, "hi": 50} # Bottleneck
        ],
        "node_caps": {}
    }
    output = run_belts_solver(input_data)
    assert output["status"] == "infeasible"
    assert "cut_reachable" in output
    assert "deficit" in output

def test_feasible_with_lower_bounds():
    """A feasible flow with non-zero lower bounds."""
    input_data = {
        "sources": {"s1": 100},
        "sink": "t1",
        "edges": [
            {"from": "s1", "to": "a", "lo": 50, "hi": 120},
            {"from": "a", "to": "t1", "lo": 50, "hi": 120}
        ],
        "node_caps": {}
    }
    output = run_belts_solver(input_data)
    assert output["status"] == "ok"
    assert abs(output["max_flow_per_min"] - 100) < 1e-9
    flow_s1_a = next(f["flow"] for f in output["flows"] if f["from"] == "s1" and f["to"] == "a")
    assert flow_s1_a >= 50 - 1e-9

def test_infeasible_due_to_lower_bounds():
    """An infeasible problem where lower bounds cannot be satisfied."""
    input_data = {
        "sources": {"s1": 100},
        "sink": "t1",
        "edges": [
            {"from": "s1", "to": "a", "lo": 0, "hi": 100},
            {"from": "a", "to": "t1", "lo": 110, "hi": 120} # Impossible lower bound
        ],
        "node_caps": {}
    }
    output = run_belts_solver(input_data)
    assert output["status"] == "infeasible"


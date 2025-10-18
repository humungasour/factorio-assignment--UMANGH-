import json
import subprocess
import sys
import os

# Use sys.executable to ensure we use the same python interpreter
PYTHON_CMD = sys.executable
FACTORY_SCRIPT = os.path.join("factory", "main.py")

def run_factory_solver(input_data):
    """Helper function to run the factory solver as a subprocess."""
    process = subprocess.run(
        [PYTHON_CMD, FACTORY_SCRIPT],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        check=False  # We will check the return code manually
    )
    if process.returncode != 0:
        raise RuntimeError(f"Factory solver failed with error:\n{process.stderr}")
    return json.loads(process.stdout)

def test_sample_case_from_pdf():
    """
    Tests the sample case, but asserts against the mathematically correct result based
    on the problem description, not the inconsistent sample output in the PDF.
    """
    input_data = {
        "machines": {
            "assembler_1": {"crafts_per_min": 30},
            "chemical": {"crafts_per_min": 60}
        },
        "recipes": {
            "iron_plate": {
                "machine": "chemical", "time_s": 3.2,
                "in": {"iron_ore": 1}, "out": {"iron_plate": 1}
            },
            "copper_plate": {
                "machine": "chemical", "time_s": 3.2,
                "in": {"copper_ore": 1}, "out": {"copper_plate": 1}
            },
            "green_circuit": {
                "machine": "assembler_1", "time_s": 0.5,
                "in": {"iron_plate": 1, "copper_plate": 3}, "out": {"green_circuit": 1}
            }
        },
        "modules": {
            "assembler_1": {"prod": 0.1, "speed": 0.15},
            "chemical": {"prod": 0.2, "speed": 0.1}
        },
        "limits": {
            "raw_supply_per_min": {"iron_ore": 5000, "copper_ore": 5000},
            "max_machines": {"assembler_1": 300, "chemical": 300}
        },
        "target": {"item": "green_circuit", "rate_per_min": 1800}
    }
    
    output = run_factory_solver(input_data)

    assert output["status"] == "ok"
    
    # Correct values based on conservation equations
    # Target: 1800 green_circuit/min. Prod bonus is 10%.
    # Crafts needed: 1800 / (1 * 1.1) = 1636.36...
    assert abs(output["per_recipe_crafts_per_min"]["green_circuit"] - 1636.3636) < 1e-3
    
    # Iron plates needed: 1636.3636. Prod bonus is 20%.
    # Crafts needed: 1636.3636 / 1.2 = 1363.6363
    assert abs(output["per_recipe_crafts_per_min"]["iron_plate"] - 1363.6363) < 1e-3

    # Copper plates needed: 3 * 1636.3636. Prod bonus is 20%.
    # Crafts needed: (3 * 1636.3636) / 1.2 = 4090.9090
    assert abs(output["per_recipe_crafts_per_min"]["copper_plate"] - 4090.9090) < 1e-3


def test_infeasible_case():
    """Tests a case that should be infeasible due to machine limits."""
    input_data = {
        "machines": {"assembler_1": {"crafts_per_min": 30}},
        "recipes": {
            "gear": {
                "machine": "assembler_1", "time_s": 0.5,
                "in": {"iron_plate": 2}, "out": {"gear": 1}
            }
        },
        "modules": {},
        "limits": {
            "raw_supply_per_min": {"iron_plate": 10000},
            "max_machines": {"assembler_1": 10} # Very low limit
        },
        "target": {"item": "gear", "rate_per_min": 5000} # Very high target
    }

    output = run_factory_solver(input_data)
    
    assert output["status"] == "infeasible"
    assert "max_feasible_target_per_min" in output
    assert output["max_feasible_target_per_min"] < 5000
    assert "assembler_1 cap" in output["bottleneck_hint"]


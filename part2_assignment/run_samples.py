import json
import subprocess
import sys

# Define the sample cases as JSON strings
FACTORY_SAMPLE_INPUT = """
{
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
            "in": {"iron_plate": 1, "copper_plate": 3},
            "out": {"green_circuit": 1}
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
"""

BELTS_SAMPLE_INPUT_OK = """
{
    "sources": {"s1": 900, "s2": 600},
    "sink": "sink",
    "edges": [
        {"from": "s1", "to": "a", "hi": 1000},
        {"from": "s2", "to": "a", "hi": 1000},
        {"from": "a", "to": "b", "hi": 900},
        {"from": "a", "to": "c", "hi": 600},
        {"from": "b", "to": "sink", "hi": 1000},
        {"from": "c", "to": "sink", "hi": 1000}
    ]
}
"""

BELTS_SAMPLE_INPUT_INFEASIBLE = """
{
    "sources": {"s1": 1000},
    "sink": "sink",
    "edges": [
        {"from": "s1", "to": "a", "hi": 1000},
        {"from": "a", "to": "sink", "hi": 500}
    ]
}
"""

def run_test(name, command, input_data_str):
    """Runs a single test case and prints the result."""
    print(f"--- Running Test: {name} ---")
    try:
        process = subprocess.run(
            command.split(),
            input=input_data_str,
            capture_output=True,
            text=True,
            check=True,
            timeout=2
        )
        output = json.loads(process.stdout)
        
        if output.get("status") == "ok" or output.get("status") == "infeasible":
            print(f"✅ PASS: Script executed successfully.")
            # print("Output:")
            # print(json.dumps(output, indent=2))
        else:
            print(f"❌ FAIL: Script returned an unexpected status: {output.get('status')}")

    except subprocess.TimeoutExpired:
        print("❌ FAIL: Script took more than 2 seconds to run.")
    except subprocess.CalledProcessError as e:
        print(f"❌ FAIL: Script returned a non-zero exit code.")
        print(f"Stderr: {e.stderr}")
    except json.JSONDecodeError:
        print("❌ FAIL: Output was not valid JSON.")
    except Exception as e:
        print(f"❌ FAIL: An unexpected error occurred: {e}")
    print("-" * (25 + len(name)))
    print()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python run_samples.py \"<factory_command>\" \"<belts_command>\"")
        print("Example: python run_samples.py \"python factory/main.py\" \"python belts/main.py\"")
        sys.exit(1)

    factory_cmd = sys.argv[1]
    belts_cmd = sys.argv[2]
    
    print("Running sample cases provided in the assignment...\n")

    # Factory Tests
    run_test("Factory Sample (OK)", factory_cmd, FACTORY_SAMPLE_INPUT)

    # Belts Tests
    run_test("Belts Sample (OK)", belts_cmd, BELTS_SAMPLE_INPUT_OK)
    run_test("Belts Sample (Infeasible)", belts_cmd, BELTS_SAMPLE_INPUT_INFEASIBLE)

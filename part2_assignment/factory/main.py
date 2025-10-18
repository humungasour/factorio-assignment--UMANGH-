import json
import sys
import numpy as np
from scipy.optimize import linprog

TOLERANCE = 1e-9

def solve_factory(data):
    """
    Solves the factory steady state problem using linear programming.
    """
    recipes = data.get("recipes", {})
    machines = data.get("machines", {})
    modules = data.get("modules", {})
    limits = data.get("limits", {})
    target_item = data["target"]["item"]
    target_rate = data["target"]["rate_per_min"]

    recipe_names = sorted(recipes.keys())
    
    # Collect all items
    all_items = set()
    for r in recipes.values():
        all_items.update(r.get("in", {}).keys())
        all_items.update(r.get("out", {}).keys())
    item_names = sorted(list(all_items))
    
    machine_types = sorted(machines.keys())
    raw_items = sorted(limits.get("raw_supply_per_min", {}).keys())

    # Identify intermediate items (produced AND consumed, not raw, not target)
    produced_items = set()
    consumed_items = set()
    for r in recipes.values():
        produced_items.update(r.get("out", {}).keys())
        consumed_items.update(r.get("in", {}).keys())
    
    intermediate_items = [item for item in item_names 
                         if item in produced_items and item in consumed_items 
                         and item not in raw_items and item != target_item]

    recipe_map = {name: i for i, name in enumerate(recipe_names)}
    item_map = {name: i for i, name in enumerate(item_names)}
    machine_map = {name: i for i, name in enumerate(machine_types)}

    num_recipes = len(recipe_names)
    num_items = len(item_names)
    num_machine_types = len(machine_types)

    # Effective crafts per minute for each recipe
    # Formula: crafts_per_min * (1+speed) / time_s
    eff_crafts = np.zeros(num_recipes)
    for i, r_name in enumerate(recipe_names):
        recipe = recipes[r_name]
        machine_name = recipe["machine"]
        machine = machines[machine_name]
        module = modules.get(machine_name, {})
        
        base_crafts_per_min = machine["crafts_per_min"]
        speed_mod = 1.0 + module.get("speed", 0.0)
        time_s = recipe["time_s"]
        
        eff_crafts[i] = base_crafts_per_min * speed_mod / time_s

    # Build item balance matrix
    A_balance = np.zeros((num_items, num_recipes))
    
    for r_idx, r_name in enumerate(recipe_names):
        recipe = recipes[r_name]
        machine_name = recipe["machine"]
        prod_bonus = 1.0 + modules.get(machine_name, {}).get("prod", 0.0)
        
        for item, amount in recipe.get("in", {}).items():
            A_balance[item_map[item], r_idx] -= amount
        
        for item, amount in recipe.get("out", {}).items():
            A_balance[item_map[item], r_idx] += amount * prod_bonus

    # Equality constraints: target item and intermediates
    A_eq_list = []
    b_eq_list = []
    
    if target_item in item_map:
        A_eq_list.append(A_balance[item_map[target_item], :])
        b_eq_list.append(target_rate)
    
    for item in intermediate_items:
        if item in item_map:
            A_eq_list.append(A_balance[item_map[item], :])
            b_eq_list.append(0.0)
    
    A_eq = np.array(A_eq_list) if A_eq_list else np.zeros((0, num_recipes))
    b_eq = np.array(b_eq_list) if b_eq_list else np.zeros(0)

    # Inequality constraints
    A_ub_parts = []
    b_ub_parts = []

    # 1. Machine caps
    machine_usage_matrix = np.zeros((num_machine_types, num_recipes))
    for r_idx, r_name in enumerate(recipe_names):
        recipe = recipes[r_name]
        m_type = recipe["machine"]
        if m_type in machine_map:
            m_idx = machine_map[m_type]
            machine_usage_matrix[m_idx, r_idx] = 1.0 / eff_crafts[r_idx]
    
    A_ub_parts.append(machine_usage_matrix)
    b_ub_parts.extend([limits.get("max_machines", {}).get(m, 1e10) for m in machine_types])

    # 2. Raw supply caps
    raw_consumption_matrix = []
    for raw_item in raw_items:
        if raw_item in item_map:
            raw_consumption_matrix.append(-A_balance[item_map[raw_item], :])
    
    if raw_consumption_matrix:
        A_ub_parts.append(np.array(raw_consumption_matrix))
        b_ub_parts.extend([limits.get("raw_supply_per_min", {}).get(r, 1e10) for r in raw_items if r in item_map])
    
    A_ub = np.vstack(A_ub_parts) if A_ub_parts else np.zeros((0, num_recipes))
    b_ub = np.array(b_ub_parts) if b_ub_parts else np.zeros(0)
    
    # Objective: Minimize total machines
    c = 1.0 / (eff_crafts + TOLERANCE)
    
    # Solve
    res = linprog(c, A_eq=A_eq, b_eq=b_eq, A_ub=A_ub, b_ub=b_ub, bounds=(0, None), method='highs')
    
    if res.success:
        return build_success_output(res.x, recipe_names, recipes, machine_types, 
                                   raw_items, item_map, eff_crafts, A_balance)

    return find_max_feasible_rate(c, A_balance, item_map, target_item, intermediate_items,
                                  A_ub, b_ub, machine_types, machine_usage_matrix,
                                  raw_items, limits)

def find_max_feasible_rate(c, A_balance, item_map, target_item, intermediate_items,
                           A_ub, b_ub, machine_types, machine_usage_matrix,
                           raw_items, limits):
    low, high = 0.0, 20000.0
    best_feasible_x = None
    best_rate = 0.0

    for _ in range(60):
        if high - low < TOLERANCE: 
            break
        
        mid = (low + high) / 2
        
        A_eq_list = []
        b_eq_list = []
        
        if target_item in item_map:
            A_eq_list.append(A_balance[item_map[target_item], :])
            b_eq_list.append(mid)
        
        for item in intermediate_items:
            if item in item_map:
                A_eq_list.append(A_balance[item_map[item], :])
                b_eq_list.append(0.0)
        
        A_eq = np.array(A_eq_list) if A_eq_list else np.zeros((0, len(c)))
        b_eq = np.array(b_eq_list) if b_eq_list else np.zeros(0)
        
        res = linprog(c, A_eq=A_eq, b_eq=b_eq, A_ub=A_ub, b_ub=b_ub, bounds=(0, None), method='highs')
        
        if res.success:
            low = mid
            best_feasible_x = res.x
            best_rate = mid
        else:
            high = mid
    
    max_rate = best_rate
    bottlenecks = []
    
    if best_feasible_x is not None:
        machine_caps = np.array([limits.get("max_machines", {}).get(m, 1e10) for m in machine_types])
        usage = machine_usage_matrix @ best_feasible_x
        for i, m_type in enumerate(machine_types):
            if usage[i] >= machine_caps[i] - TOLERANCE:
                bottlenecks.append(f"{m_type} cap")
        
        for raw_item in raw_items:
            if raw_item in item_map:
                consumption = -A_balance[item_map[raw_item], :] @ best_feasible_x
                cap = limits.get("raw_supply_per_min", {}).get(raw_item, 1e10)
                if consumption >= cap - TOLERANCE:
                    bottlenecks.append(f"{raw_item} supply")

    if not bottlenecks:
        bottlenecks.append("Complex interaction of constraints")
    
    return {
        "status": "infeasible",
        "max_feasible_target_per_min": max_rate,
        "bottleneck_hint": sorted(list(set(bottlenecks)))
    }

def build_success_output(x, recipe_names, recipes, machine_types, 
                        raw_items, item_map, eff_crafts, A_balance):
    per_recipe_crafts = {name: val if val > TOLERANCE else 0.0 
                        for name, val in zip(recipe_names, x)}
    
    per_machine_counts = {mtype: 0.0 for mtype in machine_types}
    for i, r_name in enumerate(recipe_names):
        m_type = recipes[r_name]["machine"]
        if m_type in per_machine_counts:
            machines_needed = x[i] / eff_crafts[i]
            per_machine_counts[m_type] += machines_needed

    raw_consumption = {}
    net_item_flow = A_balance @ x
    
    for item in raw_items:
        if item in item_map:
            consumption = -net_item_flow[item_map[item]]
            if consumption > TOLERANCE:
                raw_consumption[item] = consumption

    return {
        "status": "ok",
        "per_recipe_crafts_per_min": per_recipe_crafts,
        "per_machine_counts": {k: v for k, v in per_machine_counts.items() if v > TOLERANCE},
        "raw_consumption_per_min": raw_consumption
    }

def main():
    try:
        input_data = json.load(sys.stdin)
        output_data = solve_factory(input_data)
        sys.stdout.write(json.dumps(output_data, indent=2))
    except Exception as e:
        error_output = {"status": "error", "message": str(e)}
        sys.stdout.write(json.dumps(error_output, indent=2))

if __name__ == "__main__":
    main()
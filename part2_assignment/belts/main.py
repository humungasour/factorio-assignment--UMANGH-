import json
import sys
import networkx as nx

TOLERANCE = 1e-9

def solve_belts(data):
    sources = data.get("sources", {})
    sink_node = data.get("sink")
    edges = data.get("edges", [])
    node_caps = data.get("node_caps", {})
    total_supply = sum(sources.values())

    # Collect all nodes
    all_nodes = set(sources.keys()) | {sink_node}
    for edge in edges:
        all_nodes.add(edge["from"])
        all_nodes.add(edge["to"])
    
    # Node mapping for capacity constraints (node splitting)
    node_mapping = {}
    for node in all_nodes:
        if node in node_caps and node not in sources and node != sink_node:
            node_mapping[node] = (f"{node}_in", f"{node}_out")
        else:
            node_mapping[node] = (node, node)
    
    # Build the graph with node splits
    G = nx.DiGraph()
    
    # Add capacity edges for split nodes
    for node in all_nodes:
        if node in node_caps and node not in sources and node != sink_node:
            in_node, out_node = node_mapping[node]
            G.add_edge(in_node, out_node, lo=0, hi=node_caps[node])
    
    # Add original edges with mapping  
    edge_list = []
    for edge in edges:
        u, v = edge["from"], edge["to"]
        lo = edge.get("lo", 0)
        hi = edge.get("hi", float('inf'))
        
        u_node = node_mapping[u][1]  # out side
        v_node = node_mapping[v][0]  # in side
        
        G.add_edge(u_node, v_node, lo=lo, hi=hi)
        edge_list.append((u, v, u_node, v_node, lo, hi))
    
    # Calculate imbalances from lower bounds
    imbalances = {node: 0.0 for node in G.nodes()}
    for u, v, d in G.edges(data=True):
        lo = d.get('lo', 0)
        if lo > 0:
            imbalances[u] -= lo
            imbalances[v] += lo
    
    # Determine the mapped sink node (after node splitting)
    sink_mapped = node_mapping[sink_node][0]
    
    # Check if lower bounds are feasible
    if not check_lower_bound_feasibility(G, imbalances, sink_mapped):
        return {
            "status": "infeasible",
            "cut_reachable": [],
            "deficit": {"demand_balance": total_supply}
        }
    
    # Build network for main flow with adjusted capacities
    F = nx.DiGraph()
    
    # Add all edges with capacity = hi - lo
    for u, v, d in G.edges(data=True):
        lo = d.get('lo', 0)
        hi = d.get('hi', float('inf'))
        cap = hi - lo
        if cap > TOLERANCE or hi == float('inf'):
            F.add_edge(u, v, capacity=cap)
    
    # Create super source and connect to actual sources with adjusted supplies
    super_source = "_super_source"
    
    # Calculate how much supply each source has after satisfying outgoing lower bounds
    for source, supply in sources.items():
        source_node = node_mapping[source][1]
        # Negative imbalance means source is forced to send out flow
        adj_supply = supply + imbalances.get(source_node, 0)
        if adj_supply > TOLERANCE:
            F.add_edge(super_source, source_node, capacity=adj_supply)
    
    # Run max flow
    try:
        flow_value, flow_dict = nx.maximum_flow(F, super_source, sink_mapped)
    except:
        return {
            "status": "infeasible",
            "cut_reachable": [],
            "deficit": {"demand_balance": total_supply}
        }
    
    # Calculate expected flow: total supply minus what's forced out by lower bounds at sources
    source_imbalance_total = sum(imbalances.get(node_mapping[s][1], 0) for s in sources)
    expected_flow = total_supply + source_imbalance_total  # source_imbalance is negative
    
    # Check if we can route all required supply to sink
    if flow_value < expected_flow - TOLERANCE:
        cut_value, partition = nx.minimum_cut(F, super_source, sink_mapped)
        reachable, _ = partition
        
        cut_nodes = set()
        for n in reachable:
            if n == super_source:
                continue
            if "_in" in n or "_out" in n:
                base = n.rsplit("_", 1)[0]
                cut_nodes.add(base)
            else:
                cut_nodes.add(n)
        
        return {
            "status": "infeasible",
            "cut_reachable": sorted(list(cut_nodes)),
            "deficit": {"demand_balance": total_supply - flow_value}
        }
    
    # Reconstruct original flows by adding back lower bounds
    final_flows = []
    for u, v, u_node, v_node, lo, hi in edge_list:
        adjusted_flow = flow_dict.get(u_node, {}).get(v_node, 0)
        total_flow = adjusted_flow + lo
        
        if total_flow > TOLERANCE:
            final_flows.append({"from": u, "to": v, "flow": total_flow})
    
    final_flows.sort(key=lambda x: (x["from"], x["to"]))
    
    return {
        "status": "ok",
        "max_flow_per_min": total_supply,
        "flows": final_flows
    }


def check_lower_bound_feasibility(G, imbalances, sink_node):
    """
    Check if lower bounds can be satisfied using circulation.
    We need to verify that there exists a circulation that satisfies all imbalances,
    excluding the sink node which is allowed to accumulate flow.
    """
    C = nx.DiGraph()
    circ_source = "_circ_source"
    circ_sink = "_circ_sink"
    
    total_demand = 0.0
    
    # Connect circulation source/sink to nodes with imbalances (excluding sink)
    for node, imb in imbalances.items():
        # Skip the actual sink - it's allowed to have positive imbalance
        if node == sink_node:
            continue
            
        if imb > TOLERANCE:
            # Node needs flow (positive imbalance)
            C.add_edge(circ_source, node, capacity=imb)
            total_demand += imb
        elif imb < -TOLERANCE:
            # Node provides flow (negative imbalance)
            C.add_edge(node, circ_sink, capacity=-imb)
    
    # Add all edges with adjusted capacity (hi - lo)
    for u, v, d in G.edges(data=True):
        lo = d.get('lo', 0)
        hi = d.get('hi', float('inf'))
        cap = hi - lo
        if cap > TOLERANCE or hi == float('inf'):
            C.add_edge(u, v, capacity=cap)
    
    # If no imbalances (excluding sink), trivially feasible
    if total_demand < TOLERANCE:
        return True
    
    # Check if circulation can satisfy all demands
    try:
        flow_val, _ = nx.maximum_flow(C, circ_source, circ_sink)
        return abs(flow_val - total_demand) < TOLERANCE
    except:
        return False


def main():
    try:
        input_data = json.load(sys.stdin)
        output_data = solve_belts(input_data)
        sys.stdout.write(json.dumps(output_data, indent=2))
    except Exception as e:
        error_output = {"status": "error", "message": str(e)}
        sys.stdout.write(json.dumps(error_output, indent=2))

if __name__ == "__main__":
    main()
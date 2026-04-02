import os
from neo4j import GraphDatabase

def get_neo4j_driver():
    return GraphDatabase.driver(
        os.environ["NEO4J_URI"],
        auth=(os.environ["NEO4J_USER"], os.environ["NEO4J_PASSWORD"])
    )

def fetch_graph_data(node_id=None, breadcrumbs=None):
    if breadcrumbs is None:
        breadcrumbs = []

    driver = get_neo4j_driver()
    nodes_dict = {}
    edges_set = set() # Prevent visual duplicate lines
    edges_list = []

    def add_node(n, group):
        if not n: return
        name = n.get("name")
        if not name: return
        
        if name not in nodes_dict:
            nodes_dict[name] = {
                "id": name,
                "name": name,
                "summary": n.get("brief_summary", ""),
                # FIX: Use the plural array we created in Step 3
                "asset_ids": n.get("sqlite_asset_ids", []), 
                "group": group
            }
        elif group == "current":
            nodes_dict[name]["group"] = "current"
        elif group == "breadcrumb" and nodes_dict[name]["group"] != "current":
            nodes_dict[name]["group"] = "breadcrumb"

    def add_edge(source, target, relation):
        if not source or not target: return
        edge_hash = f"{source}-{relation}-{target}"
        if edge_hash not in edges_set:
            edges_set.add(edge_hash)
            edges_list.append({"source": source, "target": target, "relation": relation})

    with driver.session() as session:
        if not node_id:
            query = """
            MATCH (n:Concept)
            OPTIONAL MATCH (n)-[r]->(m:Concept)
            RETURN n, r, m, 
                   CASE WHEN r IS NOT NULL THEN startNode(r).name ELSE null END as source, 
                   CASE WHEN r IS NOT NULL THEN endNode(r).name ELSE null END as target
            LIMIT 50
            """
            result = session.run(query)
            for record in result:
                add_node(record["n"], "standard")
                add_node(record["m"], "standard")
                if record["r"]:
                    add_edge(record["source"], record["target"], record["r"].type)
        else:
            query1 = """
            MATCH (n:Concept {name: $node_id})
            OPTIONAL MATCH (n)-[r]-(m:Concept)
            RETURN n, r, m, 
                   CASE WHEN r IS NOT NULL THEN startNode(r).name ELSE null END as source, 
                   CASE WHEN r IS NOT NULL THEN endNode(r).name ELSE null END as target
            """
            result1 = session.run(query1, node_id=node_id)
            for record in result1:
                add_node(record["n"], "current")
                m = record["m"]
                if m: 
                    group = "breadcrumb" if m.get("name") in breadcrumbs else "standard"
                    add_node(m, group)
                if record["r"]:
                    add_edge(record["source"], record["target"], record["r"].type)
            
            if breadcrumbs:
                query2 = """
                MATCH (n:Concept)-[r]-(m:Concept)
                WHERE n.name IN $breadcrumbs AND m.name IN $breadcrumbs
                RETURN n, r, m, 
                       CASE WHEN r IS NOT NULL THEN startNode(r).name ELSE null END as source, 
                       CASE WHEN r IS NOT NULL THEN endNode(r).name ELSE null END as target
                """
                result2 = session.run(query2, breadcrumbs=breadcrumbs)
                for record in result2:
                    add_node(record["n"], "breadcrumb")
                    add_node(record["m"], "breadcrumb")
                    if record["r"]: 
                        add_edge(record["source"], record["target"], record["r"].type)

    driver.close()
    return {"nodes": list(nodes_dict.values()), "links": edges_list}
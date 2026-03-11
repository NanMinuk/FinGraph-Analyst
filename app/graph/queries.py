UPSERT_RELATION_QUERY = """
MERGE (h:Entity {name: $head, type: $head_type})
MERGE (t:Entity {name: $tail, type: $tail_type})
MERGE (d:Document {doc_id: $document_id})

SET d.evidence = $evidence

MERGE (h)-[r:RELATION {type: $relation, document_id: $document_id}]->(t)
SET r.confidence = $confidence,
    r.evidence = $evidence

MERGE (t)-[:EVIDENCED_BY]->(d)
"""

GET_COMPANY_RELATIONS_QUERY = """
MATCH (h:Entity {name: $company, type: "Company"})-[r:RELATION]->(t:Entity)
RETURN h.name AS head,
       h.type AS head_type,
       r.type AS relation,
       t.name AS tail,
       t.type AS tail_type,
       r.confidence AS confidence,
       r.evidence AS evidence,
       r.document_id AS document_id
LIMIT 20
"""

GET_RELEVANT_GRAPH_RELATIONS_QUERY = """
MATCH (h:Entity)-[r:RELATION]->(t:Entity)
WHERE h.name = $company
   OR t.name = $company
RETURN h.name AS head,
       h.type AS head_type,
       r.type AS relation,
       t.name AS tail,
       t.type AS tail_type,
       r.confidence AS confidence,
       r.evidence AS evidence,
       r.document_id AS document_id
LIMIT 20
"""
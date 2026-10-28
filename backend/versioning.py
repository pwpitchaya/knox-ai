"""Conservative evidence-backed document replacement, before retrieval."""
from datetime import date


def resolve_versions(records, documents, relationships, as_of):
    cutoff = date.fromisoformat(as_of)
    docs = {d['id']: d for d in documents}
    relevant = {r['document_id'] for r in records}
    excluded, audit, issues = set(), [], []
    graph = {}
    for relation in relationships:
        old, new = relation['older_id'], relation['newer_id']
        if old not in relevant and new not in relevant:
            continue
        try:
            effective = date.fromisoformat(relation['effective_from'])
        except (ValueError, TypeError):
            issues.append('ความสัมพันธ์มีวันมีผลไม่ถูกต้อง'); continue
        if effective > cutoff:
            continue
        if not relation['reviewed']:
            issues.append('ความสัมพันธ์ระหว่างฉบับยังไม่ผ่านตรวจ'); continue
        if old not in docs or new not in docs:
            issues.append('ไม่พบเอกสารที่อ้างถึงในลำดับการแก้ไข'); continue
        if not docs[new]['reviewed']:
            issues.append('เอกสารฉบับแทนที่ยังไม่ผ่านตรวจ'); continue
        start, end = docs[new]['effective_from'], docs[new].get('effective_to')
        if not start or date.fromisoformat(start) > cutoff or (end and date.fromisoformat(end) < cutoff):
            issues.append('ไม่พบฉบับแทนที่ที่ใช้ได้ ณ วันที่เลือก'); continue
        if relation['kind'] != 'REPLACES' or relation['scope'] != 'document':
            issues.append('พบการแก้ไขเฉพาะส่วน ต้องตรวจข้อความข้อกำหนดก่อนสร้างคำตอบ'); continue
        if not relation.get('evidence_excerpt') or not relation.get('source_url'):
            issues.append('ความสัมพันธ์ขาดข้อความหลักฐาน'); continue
        graph.setdefault(old, []).append(new)
        excluded.add(old)
        audit.append({'older_id': old, 'newer_id': new, 'effective_from': relation['effective_from'],
                      'evidence_excerpt': relation['evidence_excerpt'],
                      'source_url': relation['source_url'], 'pdf_page': relation.get('pdf_page')})
    if any(len(set(values)) > 1 for values in graph.values()):
        issues.append('มีเอกสารแทนที่หลายฉบับในขอบเขตเดียวกัน')
    for start in graph:
        visited, node = set(), start
        while node in graph:
            if node in visited:
                issues.append('พบวงจรในความสัมพันธ์เอกสาร'); break
            visited.add(node)
            node = graph[node][0]
    return [r for r in records if r['document_id'] not in excluded], audit, list(dict.fromkeys(issues))

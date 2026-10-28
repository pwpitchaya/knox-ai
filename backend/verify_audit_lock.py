"""Read-only integrity check of the frozen corpus; no network or AI calls."""
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parent.parent/'DOCUMENT_LIBRARY'
lock=json.loads((root/'AUDIT_LOCK.json').read_text(encoding='utf-8'))
assert len(lock['documents'])==lock['source_pdf_count']==11
assert len(set(d['sha256'] for d in lock['documents']))==11
for file,digest in [(d['file'],d['sha256']) for d in lock['documents']]:
    assert hashlib.sha256((root/file).read_bytes()).hexdigest()==digest, f'Frozen file changed: {file}'
archive=root if lock['frozen'] else root.parent/lock['baseline_snapshot']
for file,digest in lock['locked_files'].items():
    assert hashlib.sha256((archive/file).read_bytes()).hexdigest()==digest, f'Baseline changed: {file}'
answers=json.loads((root/'document_answers.json').read_text(encoding='utf-8'))
assert len(answers)==10 and all(not a['approved_for_current_answers'] for a in answers)
assert len(lock['pending_documents'])==7
catalog=json.loads((root/'catalog.json').read_text(encoding='utf-8'))
for r in catalog:
    if r.get('local_file'):assert hashlib.sha256((root/r['local_file']).read_bytes()).hexdigest()==r['sha256']
print('PASS: original 11-PDF audit baseline preserved; 10 original answer notes unchanged;',sum(r.get('downloaded',False) for r in catalog),'active PDFs verified; frozen=',lock['frozen'])

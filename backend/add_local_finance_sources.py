"""Import three existing official PDFs; never count generated notes as source documents."""
import hashlib,json,shutil
from pathlib import Path
from pypdf import PdfReader
from audit_lock import assert_collection_open

assert_collection_open()

ROOT=Path(__file__).resolve().parent.parent
IMPORT_ROOT=ROOT/'import_sources'
SOURCE=IMPORT_ROOT/'finance_family'
META=IMPORT_ROOT/'finance_clause10_documents.json'
FILES=[('KKU_R2559-finance.pdf','6FDB84D8865AF199D9B3C65544F373FB75D11E8E09972FCF7AC292EC044B4CED'),('KKU_R2564-การงบประมาณ-v.2-new.pdf','DFB56F0D0632E448E35EEF64AB17D3B69A4D61C417669A3E085337658783AFA9'),('KKU_R2565-การงบประมาณ-v.3.pdf','58A269C5A25B9407DF65BCE5B2F79DA206AF990D1D6F14D0AAAB209FD25772E9')]
metadata=json.loads(META.read_text(encoding='utf-8'));records=[]
for (filename,digest),meta in zip(FILES,metadata):
 source=SOURCE/filename
 assert hashlib.sha256(source.read_bytes()).hexdigest().upper()==digest
 target=ROOT/'DOCUMENT_LIBRARY'/'files'/filename
 shutil.copy2(source,target)
 reader=PdfReader(target)
 sections=[dict(page_number=i,text=p.extract_text() or '',needs_text_review=True,method='pypdf') for i,p in enumerate(reader.pages,1)]
 target.with_suffix('.sections.json').write_text(json.dumps(sections,ensure_ascii=False,indent=2),encoding='utf-8')
 records.append(dict(filename=filename,title=meta['title'],url=meta['officialUrl'],category='foundation',downloaded=True,local_source=target.relative_to(ROOT).as_posix(),effective_from=meta['effectiveDate'],previous_verification_scope=meta['verificationScope'],current_2026_status='not_revalidated',provenance_note='Imported from the project-relative import_sources directory; SHA matches the supplied manifest; no new network download'))
 print(filename,len(reader.pages),'pages; hash verified')
(ROOT/'DOCUMENT_LIBRARY'/'additional_sources.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copy2(SOURCE/'EVIDENCE_REVIEW.md',ROOT/'DOCUMENT_LIBRARY'/'FINANCE_PRIOR_REVIEW.md')

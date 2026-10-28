"""Synchronize public file catalog with the actual search DB; approval is excerpt-only."""
import hashlib,json,shutil,uuid
from pathlib import Path
from pypdf import PdfReader
import app as knox
from audit_lock import assert_collection_open

def main():
 assert_collection_open();root=knox.ROOT.parent/'DOCUMENT_LIBRARY'
 verified=json.loads((knox.ROOT/'verified_corpus_v2.json').read_text(encoding='utf-8'))['documents']
 checks={d['filename']:d for d in verified}
 additions=json.loads((root/'additional_sources.json').read_text(encoding='utf-8'))
 manifest=json.loads((knox.DATA/'new_sources'/'manifest.json').read_text(encoding='utf-8'))
 titles={
 'leave-authority-2569.pdf':'คำสั่ง มข. 4163/2569 มอบอำนาจเรื่องการลา',
 'salary-table-2569.pdf':'ประกาศ ก.บ.ม. 5/2569 บัญชีเงินเดือน เงินประจำตำแหน่ง และเงินค่าตอบแทนประจำตำแหน่ง',
 'salary-increase-2569.pdf':'ประกาศ ก.บ.ม. 6/2569 หลักเกณฑ์และวิธีการเลื่อนเงินเดือนประจำปี',
 'hr-amendment-2568.pdf':'ข้อบังคับการบริหารงานบุคคล (ฉบับที่ 2) พ.ศ.2568',
 'hr-amendment-2569.pdf':'ข้อบังคับการบริหารงานบุคคล (ฉบับที่ 3) พ.ศ.2569',
 'welfare-guide.pdf':'แนวปฏิบัติการขอรับเงินหรือเบิกจ่ายเงินสวัสดิการ',
 'welfare-medical-form.pdf':'แบบขอรับเงินสนับสนุนการตรวจสุขภาพประจำปีหรือค่ารักษาพยาบาล',
 'welfare-child-form.pdf':'แบบขอรับเงินสนับสนุนการศึกษาบุตรและแนวปฏิบัติ',
 'procurement-3152-2561.pdf':'หนังสือ มข. ว 3152/2561 แนวทางจัดหาพัสดุที่เกี่ยวกับการอบรมและประชุมของส่วนงาน',
 }
 for entry in manifest:
  if not entry.get('downloaded'):continue
  checked=checks.get(entry['filename'],{})
  entry.update(title=checked.get('title',titles.get(entry['filename'],entry['filename'])))
  additions=[d for d in additions if d['filename']!=entry['filename']]+[entry]
 (root/'additional_sources.json').write_text(json.dumps(additions,ensure_ascii=False,indent=2),encoding='utf-8')
 # The catalog builder also copies PDF/OCR sidecars; it never approves text.
 from finalize_document_library import main as rebuild
 rebuild()
 catalog=json.loads((root/'catalog.json').read_text(encoding='utf-8'))
 ids={}
 for entry in catalog:
  if not entry.get('local_file'):continue
  path=root/entry['local_file'];filename=path.name
  digest=hashlib.sha256(path.read_bytes()).hexdigest()
  checked=checks.get(filename)
  if checked:assert checked['sha256']==digest,'Visual evidence hash differs'
  with knox.connect() as db:
   previous=db.execute('SELECT id FROM documents WHERE sha256=?',(digest,)).fetchone()
   identifier=previous['id'] if previous else uuid.uuid4().hex
   ids[filename]=identifier
   if not previous:
    category=checked['category'] if checked else next((c for c in entry['topics'] if c in knox.CATEGORIES),'foundation')
    db.execute('''INSERT INTO documents(id,title,filename,extension,category,source_url,personnel,effective_from,reviewed,sha256,review_scope)
      VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(identifier,entry['title'],filename,'pdf',category,entry['url'],checked.get('personnel','ทุกประเภท') if checked else 'ทุกประเภท',checked.get('effective_from') if checked else None,0,digest,'pending'))
    pages=[dict(page_number=i,text=p.extract_text() or '') for i,p in enumerate(PdfReader(path).pages,1)]
    from provenance import chunk_sections
    chunks=chunk_sections(pages)
    db.executemany('INSERT INTO chunks VALUES(?,?,?,?)',[(uuid.uuid4().hex,identifier,c['text'],c['page_number']) for c in chunks])
   if checked:
    db.execute('UPDATE documents SET title=?,category=?,personnel=?,effective_from=?,reviewed=1,review_scope=? WHERE id=?',
      (checked['title'],checked['category'],checked['personnel'],checked['effective_from'],checked['review_scope']+' ตรวจภาพ 2026-10-27',identifier))
    expected=[('ข้อ '+c['clause']+' '+c['text']+(' เงื่อนไขร่วม: '+checked['conditions'] if checked['conditions'] else ''),c['page_number']) for c in checked['excerpts']]
    existing=[(r['text'],r['page_number']) for r in db.execute('SELECT text,page_number FROM chunks WHERE document_id=? ORDER BY rowid',(identifier,))]
    if existing!=expected:
     db.execute('DELETE FROM chunks WHERE document_id=?',(identifier,))
     db.executemany('INSERT INTO chunks VALUES(?,?,?,?)',[(uuid.uuid4().hex,identifier,text,page) for text,page in expected])
    db.execute('INSERT OR REPLACE INTO document_audits VALUES(?,?,?,?,?)',(identifier,int(checked['current_verified']),checked['checked_at'],digest,checked['review_scope']))
  shutil.copy2(path,knox.DATA/'files'/(identifier+'.pdf'))
 # Record the actual whole-document repeals stated on page 1 of the new PDFs.
 with knox.connect() as db:
  for old,new in [('leave-employees-2565.pdf','leave-employees-2569.pdf'),('leave-workers-2565.pdf','leave-workers-2569.pdf')]:
   if old in ids and new in ids:
    checked=checks[new]
    db.execute('INSERT OR REPLACE INTO version_relationships VALUES(?,?,?,?,?,?,?,?,?,?)',
     ('verified-'+new,ids[old],ids[new],'REPLACES','document',checked['effective_from'],checked['source_url'],1,'ข้อ 3 ให้ยกเลิกประกาศการลาฉบับเดิม '+('6/2565' if 'employees' in old else '7/2565'),1))
    db.execute('UPDATE documents SET reviewed=0,effective_to=?,review_scope=? WHERE id=?',('2026-02-12','Historical: repealed by 2569 document',ids[old]))
 with knox.connect() as db:
  print('Search DB:',db.execute('SELECT COUNT(*) FROM documents').fetchone()[0],'documents;',db.execute('SELECT COUNT(*) FROM chunks JOIN documents d ON d.id=document_id WHERE d.reviewed=1').fetchone()[0],'reviewed excerpts')
 (root/'coverage_policy.json').write_text(json.dumps(dict(reviewed_numbers=[d['number'] for d in verified],current_numbers=[d['number'] for d in verified if d['current_verified']],checked_at='2026-10-27',scope='only manually transcribed visually checked excerpts; not every provision'),ensure_ascii=False,indent=2),encoding='utf-8')
 # Enrich catalog display without changing the approval state of pending files.
 for entry in catalog:
  name=Path(entry.get('local_file','')).name
  if name in checks:
   d=checks[name];entry.update(title=d['title'],personnel=d['personnel'],effective_from=d['effective_from'],verified_excerpts=len(d['excerpts']),checked_at=d['checked_at'],current_verified=d['current_verified'],approved_for_current_answers=d['current_verified'],status='มีข้อความตรวจเทียบภาพตามขอบเขต — ไม่ใช่รับรองทั้งฉบับ')
 (root/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':main()

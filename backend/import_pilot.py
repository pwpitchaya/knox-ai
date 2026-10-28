"""Idempotently import actual source files and only visually checked excerpts."""
import hashlib
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import app as knox
from provenance import chunk_sections, extract_sections


def main():
    from audit_lock import assert_collection_open
    assert_collection_open()
    candidates = knox.DATA / 'candidates'
    catalog = json.loads((candidates/'catalog.json').read_text(encoding='utf-8'))
    catalog += json.loads((candidates/'hr-catalog.json').read_text(encoding='utf-8'))
    curated = json.loads((knox.ROOT/'reviewed_excerpts.json').read_text(encoding='utf-8'))
    approved = {d['filename']: d for d in curated['documents']}
    if knox.DB.exists():
        shutil.copy2(knox.DB, knox.DATA / ('backup-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.sqlite3'))
    ids = {}
    # These two HR files are copies of the same regulation, not two independent
    # documents. Keep the scanned variant as an OCR audit artifact only.
    duplicate = candidates/'hr-2565.pdf'
    if duplicate.exists():
        digest = hashlib.sha256(duplicate.read_bytes()).hexdigest()
        with knox.connect() as db:
            db.execute('DELETE FROM documents WHERE sha256=?',(digest,))
    titles = {
        'leave-employees-2559.pdf':'ประกาศ ก.บ.ม. 2/2559 การลาของพนักงาน (ฉบับยกเลิกแล้ว)',
        'leave-workers-2565.pdf':'ประกาศ ก.บ.ม. 7/2565 การลาและเงินเดือนระหว่างลาของลูกจ้างมหาวิทยาลัย',
        'salary-increase-2566.pdf':'ประกาศ ก.บ.ม. 8/2566 หลักเกณฑ์และวิธีการเลื่อนเงินเดือนประจำปี',
        'study-leave-2566.pdf':'ประกาศ ก.บ.ม. 10/2566 หลักเกณฑ์การไปศึกษา ฝึกอบรม ปฏิบัติการวิจัย และดูงาน',
    }
    for entry in catalog:
        if entry['filename']=='hr-2565.pdf':
            continue
        if not entry.get('downloaded'):
            continue
        source = candidates/entry['filename']
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        checked = approved.get(entry['filename'])
        can_approve = bool(checked and checked.get('allowed_for_current_answers', True))
        sidecar = source.with_suffix('.sections.json')
        if checked:
            sections = checked['excerpts']
            chunks = [{'text':s['text'], 'page_number':s['page_number']} for s in sections]
        elif sidecar.exists():
            sections = json.loads(sidecar.read_text(encoding='utf-8'))
            chunks = chunk_sections(sections)
        else:
            sections = extract_sections(str(source), 'pdf')
            sidecar.write_text(json.dumps(sections,ensure_ascii=False,indent=2),encoding='utf-8')
            chunks = chunk_sections(sections)
        with knox.connect() as db:
            previous = db.execute('SELECT id FROM documents WHERE sha256=?',(digest,)).fetchone()
            identifier = previous['id'] if previous else uuid.uuid4().hex
            meta = checked or entry
            title = meta.get('title', entry['filename'])
            title = titles.get(entry['filename'],title)
            url = entry.get('url') or meta.get('source_url')
            scope = ('เฉพาะข้อความถอดจากภาพที่ตรวจแล้ว หน้า '+','.join(str(n) for n in sorted({s['page_number'] for s in sections}))
                     + '; ไม่รับรองความครบถ้วนของฉบับแก้ไข' if can_approve else 'ประวัติ/รอตรวจ ไม่ใช้ตอบสิทธิปัจจุบัน')
            fields = (title,entry['filename'],'pdf',meta['category'],url,meta.get('personnel','ทุกประเภท'),
                      meta.get('effective_from') or None,int(can_approve),digest,scope)
            if previous:
                db.execute('''UPDATE documents SET title=?,filename=?,extension=?,category=?,source_url=?,
                  personnel=?,effective_from=?,reviewed=?,sha256=?,review_scope=? WHERE id=?''',fields+(identifier,))
            else:
                db.execute('''INSERT INTO documents
                  (title,filename,extension,category,source_url,personnel,effective_from,reviewed,sha256,review_scope,id)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?)''',fields+(identifier,))
            db.execute('DELETE FROM chunks WHERE document_id=?',(identifier,))
            db.executemany('INSERT INTO chunks VALUES (?,?,?,?)',
                           [(uuid.uuid4().hex,identifier,c['text'],c['page_number']) for c in chunks])
        shutil.copy2(source,knox.DATA/'files'/f'{identifier}.pdf')
        ids[entry['filename']]=identifier
        print(entry['filename'],'chunks',len(chunks),'reviewed',bool(checked),flush=True)
    if all(n in ids for n in ['leave-employees-2559.pdf','leave-employees-2565.pdf']):
        with knox.connect() as db:
            db.execute('''INSERT OR IGNORE INTO version_relationships VALUES (?,?,?,?,?,?,?,?,?,?)''',
              ('leave-2559-to-2565',ids['leave-employees-2559.pdf'],ids['leave-employees-2565.pdf'],
               'REPLACES','document','2022-10-27',
               next(e['url'] for e in catalog if e['filename']=='leave-employees-2565.pdf'),1,
               approved['leave-employees-2565.pdf']['excerpts'][0]['text'],1))
    (knox.DATA/'pilot-import.json').write_text(json.dumps({'ids':ids,'approved_excerpt_documents':list(approved)},ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()

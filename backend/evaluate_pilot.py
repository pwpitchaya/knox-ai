"""Actual corpus retrieval evaluation; live generation only if configured."""
import json
import os
from datetime import date
from pathlib import Path
import app as knox

CASES = [
    ('ลาป่วยตั้งแต่กี่วันต้องมีใบรับรองแพทย์','leave','ใบรับรองแพทย์',3),
    ('ลาป่วยได้รับเงินเดือนระหว่างลากี่วัน','leave','๖๐ วันทำการ',3),
    ('เริ่มงานไม่ถึง 6 เดือน ลาป่วยได้เงินเดือนกี่วัน','leave','๓๐ วันทำการ',3),
    ('ลากิจส่วนตัวปีแรกได้รับเงินเดือนกี่วัน','leave','๑๕ วันทำการ',4),
    ('ลากิจส่วนตัวปีงบประมาณหนึ่งได้กี่วัน','leave','๔๕ วันทำการ',4),
    ('ลาพักผ่อนสะสมได้กี่วัน','leave','๒๐ วันทำการ',4),
    ('ลาคลอดบุตรได้รับเงินเดือนกี่วัน','leave','๙๘ วัน',3),
    ('ลาไปช่วยเหลือภริยาคลอดบุตรต้องแนบเอกสารอะไร','leave','ใบสูติบัตร',4),
    ('รถส่วนตัวไปราชการต้องขออนุมัติก่อนไหม','travel','ได้รับอนุมัติ',4),
    ('รถยนต์ส่วนบุคคลเบิกกิโลเมตรละเท่าไหร่','travel','กิโลเมตรละ 4 บาท',5),
    ('รถจักรยานยนต์ส่วนบุคคลเบิกกิโลเมตรละเท่าไหร่','travel','กิโลเมตรละ 2 บาท',5),
]


def main():
    report = {'corpus':'actual visually checked pilot excerpts',
              'generation_configured':all(knox.ai_config()),
              'generation_note':'Live answers not evaluated unless a usable API key and model are configured.',
              'cases':[]}
    for index,(question,category,phrase,page) in enumerate(CASES):
        # KNOX_SEMANTIC=0 is the lexical baseline; =1 evaluates cached E5 hybrid.
        # Neither retrieval score is a generated-answer accuracy score.
        response = knox.ask(knox.Question(question=question,personnel='พนักงานมหาวิทยาลัย',category=category,as_of=date(2026,10,27)))
        sources = response.get('sources',[])
        passed = any(phrase in s['text'] and s['page_number']==page for s in sources)
        row = {'question':question,'expected_phrase':phrase,'expected_page':page,
               'retrieval_hit_at_6':passed,'status':response['status'],
               'retrieval':response.get('retrieval'),'version_audit':response.get('version_audit',[]),
               'source_pages':[s['page_number'] for s in sources]}
        if response['status']=='answered':
            row['answer']=response['answer'];row['citations']=response['citations']
        report['cases'].append(row)
        print(index+1,'hit',passed,'status',response['status'],flush=True)
    report['retrieval_hits_at_6']=sum(r['retrieval_hit_at_6'] for r in report['cases'])
    report['total']=len(CASES)
    report['answer_accuracy']='not measured; requires independent answer review'
    report['semantic_enabled']=os.getenv('KNOX_SEMANTIC','1')=='1'
    destination=knox.ROOT.parent/('PILOT_EVALUATION_HYBRID.json' if report['semantic_enabled'] else 'PILOT_EVALUATION.json')
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Report',destination.name,report['retrieval_hits_at_6'],'/',report['total'])


if __name__=='__main__':main()

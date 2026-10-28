"""Explicit live integration check. Never print credentials."""
import json
from pathlib import Path
import app as knox


def main():
    destination=knox.ROOT.parent/'AI_VERIFICATION.json'
    key,model=knox.ai_config()
    report={'model':model,'configured':bool(key and model),'live_answer_tested':False}
    if not key or not model:
        report['status']='blocked_missing_api_configuration'
        report['missing']=[n for n,v in [('OPENAI_API_KEY',key),('OPENAI_MODEL',model)] if not v]
    else:
        from fastapi import HTTPException
        try:
            response=knox.ask(knox.Question(question='ลาป่วยตั้งแต่กี่วันต้องมีใบรับรองแพทย์',
                                            personnel='พนักงานมหาวิทยาลัย',category='leave',as_of='2026-10-27'))
            report['status']=response['status']
            report['live_answer_tested']=response['status']=='answered'
            report['answer']=response.get('answer')
            report['citations']=response.get('citations',[])
            report['sources']=[{'citation':s['citation'],'title':s['title'],'page':s['page_number']} for s in response.get('sources',[])]
            if report['live_answer_tested']:
                normalized=response['answer'].translate(str.maketrans('๐๑๒๓๔๕๖๗๘๙','0123456789'))
                report['expected_number_3_present']='3' in normalized
                report['answer_needs_human_review']=True
        except HTTPException as error:
            report['status']='live_api_error'
            report['http_status']=error.status_code
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in {'answer','sources'}},ensure_ascii=False))


if __name__=='__main__':main()

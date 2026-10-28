"""Source-backed retrieval and generated-answer evaluation with explicit limitations."""
import argparse,json,os,re,time,statistics
from pathlib import Path
from unittest.mock import patch
import app as knox
from fastapi import HTTPException

ROOT=knox.ROOT
def normal(text):
 return re.sub(r'[\s,]','',text.translate(str.maketrans('๐๑๒๓๔๕๖๗๘๙','0123456789'))).lower()

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['lexical','hybrid','live'],default='lexical');parser.add_argument('--limit',type=int,default=60);parser.add_argument('--fresh',action='store_true')
 args=parser.parse_args();cases=json.loads((ROOT/'evaluation_cases_v2.json').read_text(encoding='utf-8'))[:args.limit]
 os.environ['KNOX_EVALUATION_DIAGNOSTICS']='1'
 os.environ['KNOX_EVAL_BYPASS_CACHE']='1' if args.fresh else '0'
 os.environ['KNOX_SEMANTIC']='0' if args.mode=='lexical' else '1'
 knox._model_attempted=False;knox._model=None
 with knox.connect() as db:files={r['id']:r['filename'] for r in db.execute('SELECT id,filename FROM documents')}
 out=ROOT/'data'/'evaluations';out.mkdir(exist_ok=True)
 report=dict(mode=args.mode,cache_bypassed=args.fresh,dataset='evaluation_cases_v2.json',reference_basis='Manually authored development-set checks against visually inspected source pages; not an independent human study or held-out accuracy',cases=[],answer_accuracy_is_limited_to='automated key facts + expected evidence citation; not exhaustive semantic correctness or user acceptance')
 def save():
  rows=report['cases'];positive=[r for r in rows if r['expected']=='answered'];negative=[r for r in rows if r['expected']!='answered']
  report['summary']=dict(completed=len(rows),positive=len(positive),negative=len(negative),retrieval_hits=sum(r.get('retrieval_hit',False) for r in positive),negative_correct=sum(r.get('passed',False) for r in negative),end_to_end_passes=sum(r.get('passed',False) for r in positive) if args.mode=='live' else None,errors=sum('error' in r for r in rows),mean_ms=round(statistics.mean(r['elapsed_ms'] for r in rows),1) if rows else None,cached_answers=sum(r.get('cached',False) for r in rows),input_tokens=sum(r.get('usage',{}).get('input_tokens',0) for r in rows if not r.get('cached')),output_tokens=sum(r.get('usage',{}).get('output_tokens',0) for r in rows if not r.get('cached')))
  (out/f'{args.mode}-v2.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
 context=patch('app.generation_enabled',return_value=False) if args.mode!='live' else patch('app.generation_enabled',return_value=True)
 with context:
  for case in cases:
   started=time.perf_counter();row=dict(case)
   try:
    response=knox.ask(knox.Question(**{k:case[k] for k in ['question','personnel','category','as_of','evidence_scope']}))
    row.update(status=response['status'],answer=response.get('answer'),citations=response.get('citations',[]),cached=response.get('cached',False),usage=response.get('usage',{}),retrieval=response.get('retrieval'),validation_repairs=response.get('validation_repairs',0))
    sources=response.get('sources',[])
    row['source_references']=[dict(citation=s['citation'],file=files.get(s['document_id']),page=s['page_number']) for s in sources]
    if case['expected']=='answered':
     correct=[s for s in sources if files.get(s['document_id'])==case['gold_document'] and s['page_number']==case['gold_page'] and normal(case['gold_needle']) in normal(s['text'])]
     row['retrieval_hit']=bool(correct)
     row['key_facts_pass']=all(any(normal(term) in normal(response.get('answer','')) for term in group) for group in case['answer_term_groups'])
     row['gold_citation_pass']=any(s['citation'] in response.get('citations',[]) for s in correct)
     row['passed']=response['status']=='answered' and row['key_facts_pass'] and row['gold_citation_pass'] if args.mode=='live' else row['retrieval_hit']
    else:row['passed']=response['status']==case['expected'] and not response.get('citations')
   except HTTPException as e:row.update(status='error',error=str(e.detail),passed=False)
   except Exception as e:row.update(status='error',error=type(e).__name__,passed=False)
   row['elapsed_ms']=round((time.perf_counter()-started)*1000,1);report['cases'].append(row);save()
   print(args.mode,case['id'],row['status'],'pass',row['passed'],flush=True)
   if 'error' in row and any(w in row['error'] for w in ['เครดิต','API key']):
    report['stopped_reason']=row['error'];save();break
 print(json.dumps(report['summary'],ensure_ascii=False),flush=True)

if __name__=='__main__':main()

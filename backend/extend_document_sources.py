"""Extend source discovery without calling AI or claiming downloads succeeded."""
import concurrent.futures
import json
from pathlib import Path
import build_document_library as lib

EXTRA = [
 'https://hr2.kku.ac.th/?page_id=5351',
 'https://hr2.kku.ac.th/?page_id=13038',
 'https://finweb.kku.ac.th/fn_news2/',
 'https://finweb.kku.ac.th/kku_an_625_64/',
 'https://finweb.kku.ac.th/kku_an_191_64/',
 'https://is.kku.ac.th/nkc2021/personal/default/view?id=2269',
]


def main():
 from audit_lock import assert_collection_open
 assert_collection_open()
 root=lib.ROOT
 sources=json.loads((root/'source_pages.json').read_text(encoding='utf-8'))
 with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
  for record,links in pool.map(lib.read_page,EXTRA):
   sources=[s for s in sources if s['url']!=record['url']]+[record]
   print(record['url'],record.get('error','archived'),flush=True)
 (root/'source_pages.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding='utf-8')
 found={}
 for source in sources:
  if 'archive' not in source:continue
  parser=lib.Parser(source.get('final_url',source['url']))
  parser.feed((root/source['archive']).read_text(encoding='utf-8',errors='replace'))
  for link in parser.links:
   text=link['label']+' '+link['context']+' '+link['url']
   if lib.attachment(link['url']) and lib.official(link['url']) and lib.topics(text):
    item=found.setdefault(link['url'],dict(url=link['url'],labels=[],contexts=[],index_urls=[],topics=[]))
    for key,value in [('labels',link['label']),('contexts',link['context']),('index_urls',source['url'])]:
     if value and value not in item[key]:item[key].append(value)
    item['topics']=sorted(set(item['topics']+lib.topics(text)))
 (root/'discovered_links.json').write_text(json.dumps(list(found.values()),ensure_ascii=False,indent=2),encoding='utf-8')
 print('All source-linked candidates',len(found))


if __name__=='__main__':main()

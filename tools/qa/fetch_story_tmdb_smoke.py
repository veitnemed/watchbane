from pathlib import Path
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json,re,requests
import argparse
parser=argparse.ArgumentParser(description="Small developer-only public-page smoke, no API token or retries. Does not bypass denied access.")
parser.add_argument("--output-dir",type=Path,required=True)
parser.add_argument("--allow-public-pages",action="store_true")
args=parser.parse_args()
if not args.allow_public_pages:parser.error("Pass --allow-public-pages to request 24 public pages for local testing")
root=args.output_dir;root.mkdir(parents=True,exist_ok=True)
rows=[('tv',1396,'Breaking Bad'),('tv',60059,'Better Call Saul'),('tv',67744,'Mindhunter'),('tv',1405,'Dexter'),('tv',63351,'Narcos'),('tv',69740,'Ozark'),('movie',286217,'The Martian'),('movie',137,'Groundhog Day'),('movie',77,'Memento'),('movie',278,'The Shawshank Redemption'),('tv',95396,'Severance'),('movie',157336,'Interstellar')]
class Overview(HTMLParser):
 def __init__(self):super().__init__();self.depth=0;self.parts=[];self.title_parts=[];self.in_title=False
 def handle_starttag(self,tag,attrs):
  if tag=='title':self.in_title=True
  if tag=='div':
   if self.depth:self.depth+=1
   elif 'overview' in dict(attrs).get('class','').split():self.depth=1
 def handle_endtag(self,tag):
  if tag=='div' and self.depth:self.depth-=1
  if tag=='title':self.in_title=False
 def handle_data(self,data):
  if self.depth:self.parts.append(data)
  if self.in_title:self.title_parts.append(data)
def fetch(args):
 kind,id,title,lang=args;url=f'https://www.themoviedb.org/{kind}/{id}?language={lang}'
 record=dict(key=f'{kind}:{id}',title=title,media_type=kind,language=lang,source=url)
 try:
  response=requests.get(url,timeout=(15,35));record['status']=response.status_code
  if response.status_code!=200:return record
  parser=Overview();parser.feed(response.text)
  overview=' '.join(' '.join(parser.parts).split())
  record.update(page_title=''.join(parser.title_parts),overview=overview,overview_sha256=sha256(overview.encode()).hexdigest(),actual_language='ru' if re.search('[а-яА-Я]',overview) else 'en',fetched_date='2026-11-19')
 except requests.RequestException as e:record['error']=type(e).__name__
 print(kind,id,lang,record.get('status'),len(record.get('overview','')),flush=True)
 return record
with ThreadPoolExecutor(max_workers=3) as executor:
 results=list(executor.map(fetch,[(k,i,t,l) for k,i,t in rows for l in ('ru-RU','en-US')]))
(root/'corpus.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
print('valid',sum(bool(r.get('overview')) for r in results),'of',len(results),flush=True)

"""Fresh-process passage-cache speed probe. Outputs timings/hashes, never synopsis text."""
import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir',type=Path,required=True)
    parser.add_argument('--profile',type=Path,required=True,help='Disposable NEW profile directory')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--corpus',type=Path,help='Optional external genuine descriptions; never copied to output')
    parser.add_argument('--count',type=int,default=120)
    parser.add_argument('--worker',choices=['baseline','populate','restart','changed'])
    args=parser.parse_args()
    if not args.worker:
        if args.profile.exists():parser.error('Use a new disposable profile directory')
        reports=[]
        for mode in ['baseline','populate','restart','changed']:
            command=[sys.executable,'-m','tools.qa.benchmark_story_cache','--model-dir',str(args.model_dir),
                     '--profile',str(args.profile),'--output',str(args.output),'--count',str(args.count),'--worker',mode]
            if args.corpus:command += ['--corpus',str(args.corpus)]
            result=subprocess.run(command,capture_output=True,text=True,check=True)
            reports.append(json.loads(result.stdout))
        report={'runs':reports,'notes':'Fresh Linux processes; CPU FP32. Expanded descriptions with synthetic suffixes, not a quality benchmark. OS page cache is uncontrolled. No corpus text exported.'}
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2));return
    start=perf_counter()
    from candidates.story_search import StoryDocument
    from tests.fixtures.story_demo import demo_documents
    from candidates.story_semantic import LocalE5,SemanticStorySearch
    from candidates.story_vector_cache import CachedPassageEncoder
    if args.corpus:
        raw=json.loads(args.corpus.read_text())
        base=[StoryDocument(r['key'],r['title'],r['overview'],r['media_type'],'external') for r in raw if r.get('language')=='ru-RU' and r.get('overview')]
    else:base=list(demo_documents())
    docs=[replace(base[i%len(base)],key=f'probe:{i}',overview=base[i%len(base)].overview+f' Тестовая запись номер {i}.') for i in range(args.count)]
    if args.worker=='changed':docs[-1]=replace(docs[-1],overview=docs[-1].overview+' Изменение текста.')
    loaded=perf_counter();encoder=LocalE5(args.model_dir);load_ms=(perf_counter()-loaded)*1000
    if args.worker!='baseline':encoder=CachedPassageEncoder(encoder,args.profile)
    begin=perf_counter();engine=SemanticStorySearch(docs,encoder);index_ms=(perf_counter()-begin)*1000
    before_search={'hits':encoder.cache.hits,'misses':encoder.cache.misses,'writes':encoder.cache.writes,'errors':encoder.cache.errors} if args.worker!='baseline' else {}
    begin=perf_counter();result=engine.search('сериал про преступника');search_ms=(perf_counter()-begin)*1000
    import resource
    report={'mode':args.worker,'count':len(docs),'model_load_ms':load_ms,'index_ms':index_ms,'search_ms':search_ms,
            'total_ms':(perf_counter()-start)*1000,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'index_cache':before_search,'vector_sha256':sha256(engine.vectors.tobytes()).hexdigest(),
            'top5':[(h.document.key,h.score,sha256(h.evidence.encode()).hexdigest()) for h in result.hits]}
    print(json.dumps(report))


if __name__=='__main__':main()

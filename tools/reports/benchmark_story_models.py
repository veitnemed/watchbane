"""TMDb public-page LOCAL smoke. Accept external JSON; never export synopsis text."""
import argparse
from hashlib import sha256
import json
from math import log2
from pathlib import Path
import platform
from statistics import mean, median
from time import perf_counter
from candidates.story_search import StoryDocument, StorySearch, media_constraints
from candidates.story_semantic import LocalE5, SemanticStorySearch
from candidates.story_lexical import LexicalIndex

# Queries/labels fixed before the E5 TMDb run. No tuning or learned parameters.
CASES=[
("roles","сериал про преступника",["tv:1396","tv:1405","tv:63351","tv:69740"]),
("roles","сериал про следователей, которые изучают мышление убийц",["tv:67744"]),
("roles","эксперт полиции сам тайно убивает людей",["tv:1405"]),
("typo","сериал про пристурника",["tv:1396","tv:1405","tv:63351","tv:69740"]),
("typo","астронафт выживает на другой планете",["movie:286217"]),
("short","отмывание денег",["tv:69740"]),
("short","амнезия",["movie:77"]),
("paraphrase","школьный педагог начинает зарабатывать на запрещенных веществах",["tv:1396"]),
("paraphrase","человек легализует доходы картеля, чтобы спасти близких",["tv:69740"]),
("paraphrase","юрист постепенно теряет моральные принципы",["tv:60059"]),
("paraphrase","мужчина не может запоминать новые события",["movie:77"]),
("paraphrase","день снова начинается после каждого пробуждения",["movie:137"]),
("conflict","герой остался один на Марсе и пытается дождаться помощи",["movie:286217"]),
("conflict","работники не помнят свою личную жизнь в офисе",["tv:95396"]),
("conflict","банкир сохраняет надежду и дружбу за решеткой",["movie:278"]),
("conflict","отец покидает детей и летит искать новый дом для человечества",["movie:157336"]),
("explicit_type","фильм о повторяющемся дне",["movie:137"]),
("explicit_year","фильм 2014 про поиск нового дома в космосе",["movie:157336"]),
]
YEARS={"tv:1396":2008,"tv:60059":2015,"tv:67744":2017,"tv:1405":2006,"tv:63351":2015,"tv:69740":2017,
       "movie:286217":2015,"movie:137":1993,"movie:77":2000,"movie:278":1994,"tv:95396":2022,"movie:157336":2014}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus",type=Path,required=True)
    parser.add_argument("--model-dir",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--repeats",type=int,default=5)
    args=parser.parse_args()
    raw=json.loads(args.corpus.read_text())
    if raw and "requested_locale" in raw[0]:
        # Independent reviewer schema. Keep the original external corpus intact.
        raw=[{**r, "key":f"{r['media_type']}:{r['tmdb_id']}",
              "language":"ru-RU" if r.get("overview_language", "").startswith("ru") else "en-US",
              "source":r["source_url"]} for r in raw]
    start=perf_counter();encoder=LocalE5(args.model_dir);load_ms=(perf_counter()-start)*1000
    output={"kind":"local public-page smoke; NOT TMDb API or independent catalog benchmark", "python":platform.python_version(),
            "platform":platform.platform(),"model_variant":encoder.variant,"corpus_sha256":sha256(args.corpus.read_bytes()).hexdigest(),
            "model_load_ms":load_ms,"repeats":args.repeats,"sources":[],"summary":[],"queries":[],"index_ms":{}}
    for lang in ("ru-RU","en-US"):
        records=[r for r in raw if r.get("overview") and r.get("language")==lang]
        docs=[StoryDocument(r["key"],r["title"],r["overview"],r["media_type"],r["source"],year=YEARS.get(r["key"])) for r in records]
        for r in records: output["sources"].append({k:v for k,v in r.items() if k!="overview"})
        start=perf_counter();engine=SemanticStorySearch(docs,encoder);output["index_ms"][lang]=(perf_counter()-start)*1000
        if not docs: continue
        lexical=LexicalIndex(docs);fallback=StorySearch(docs)
        def lexical_search(query):
            kind,year=media_constraints(query)
            scores=lexical.scores(query)
            return [docs[i].key for i in sorted(range(len(docs)),key=lambda i:(-scores[i],docs[i].key))
                    if scores[i]>0 and (not kind or docs[i].media_type==kind) and (not year or docs[i].year==year)]
        methods={
            "text_char_tfidf":lexical_search,
            "dictionary_fallback":lambda q:[h.document.key for h in fallback.search(q,limit=10).hits],
            "e5_raw":lambda q:[h.document.key for h in engine.search(q,limit=10,rerank=False,hybrid=False,domain_filters=False,repair_typos=False,evidence=False).hits],
            "e5_explicit_constraints":lambda q:[h.document.key for h in engine.search(q,limit=10,rerank=False,hybrid=False,repair_typos=False,evidence=False).hits],
            "e5_hybrid":lambda q:[h.document.key for h in engine.search(q,limit=10,rerank=False,evidence=False,role_adjustment=False).hits],
            "e5_hybrid_role":lambda q:[h.document.key for h in engine.search(q,limit=10,rerank=False,evidence=False,role_adjustment=True).hits],
            "e5_hybrid_plot_rerank":lambda q:[h.document.key for h in engine.search(q,limit=10,rerank=True).hits],
        }
        available={d.key for d in docs}
        for method,search in methods.items():
            for group,query,labels in CASES:
                relevant=set(labels)&available
                if not relevant:continue
                timings=[]
                start=perf_counter();found=search(query);cold=(perf_counter()-start)*1000
                for _ in range(args.repeats):
                    start=perf_counter();found=search(query);timings.append((perf_counter()-start)*1000)
                hits=[int(k in relevant) for k in found[:5]]
                ideal=sum(1/log2(i+2) for i in range(min(5,len(relevant))))
                output["queries"].append(dict(language=lang,method=method,group=group,query=query,relevant=sorted(relevant),
                    top5=found[:5],hit_at_1=int(bool(hits) and hits[0]),hit_at_3=int(any(hits[:3])),
                    precision_at_5=sum(hits)/5,recall_at_5=sum(hits)/len(relevant),
                    ndcg_at_5=sum(h/log2(i+2) for i,h in enumerate(hits))/ideal,
                    retrieval_recall_at_10=len(set(found[:10])&relevant)/len(relevant),
                    first_ms=cold,median_ms=median(timings),p95_ms=sorted(timings)[max(0,int(.95*len(timings))-1)]))
        for method in methods:
            for group in ["all",*dict.fromkeys(c[0] for c in CASES)]:
                rows=[r for r in output["queries"] if r["language"]==lang and r["method"]==method and (group=="all" or r["group"]==group)]
                if not rows:continue
                row=dict(language=lang,method=method,group=group,queries=len(rows),documents=len(docs))
                for metric in ("hit_at_1","hit_at_3","precision_at_5","recall_at_5","ndcg_at_5","retrieval_recall_at_10","first_ms","median_ms","p95_ms"):
                    row[metric]=round(mean(r[metric] for r in rows),4)
                output["summary"].append(row)
                if group=="all":print(row,flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n")
    print("No synopsis text written to report.")

if __name__=="__main__":main()

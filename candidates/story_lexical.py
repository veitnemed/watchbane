"""Character TF-IDF baseline: morphology/typo tolerance, no semantic lexicon."""
from collections import Counter
from math import log, sqrt
from candidates.story_search import tokens, STOP


def grams(text):
    text=" ".join(w for w in tokens(text) if w not in STOP)
    return Counter(text[i:i+n] for n in (3,4,5) for i in range(max(0,len(text)-n+1)))


class LexicalIndex:
    def __init__(self,documents):
        counts=[grams(d.overview) for d in documents]
        df=Counter(g for c in counts for g in c)
        self.idf={g:log((1+len(counts))/(1+count))+1 for g,count in df.items()}
        self.vectors=[self.vector(c) for c in counts]

    def vector(self,counts):
        v={g:(1+log(count))*self.idf[g] for g,count in counts.items() if g in self.idf}
        norm=sqrt(sum(x*x for x in v.values())) or 1
        return {g:x/norm for g,x in v.items()}

    def scores(self,query):
        q=self.vector(grams(query))
        return [sum(value*v.get(g,0) for g,value in q.items()) for v in self.vectors]

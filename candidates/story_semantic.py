"""Local E5 ONNX + lexical hybrid retrieval and sentence/lead plot reranking.

No HTTP client, Hub loader, remote code, pickle or automatic download. Model files
must already exist and match the publisher checksums. Personal text stays in RAM.
"""
from collections import OrderedDict
from pathlib import Path
import re
from threading import RLock
from candidates.story_model_manifest import FILES, PORTABLE_FILES, artifact_sha256
import sys
from candidates.story_search import (StoryHit, StoryResponse, tokens, STOP, ROLE_WORDS,
                                     concepts, protagonist, lexical_score, unsupported_negation, media_constraints, requested_protagonist,
                                     instructional_non_plot, OUT_OF_SCOPE_NOTICE)
from candidates.story_lexical import LexicalIndex


class LocalE5:
    def __init__(self, directory: str | Path):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.np=np
        directory=Path(directory)
        files=PORTABLE_FILES if (directory/"onnx/model.onnx").exists() else FILES
        self.variant="fp32" if files is PORTABLE_FILES else "int8-vnni"
        if sys.platform == "win32" and self.variant != "fp32":
            raise ValueError("Windows requires the portable FP32 model; the VNNI development artifact is not validated")
        for name,digest in files.items():
            file=directory/name
            if not file.is_file() or artifact_sha256(file)!=digest:
                raise ValueError("Missing or unverified local E5 artifact: " + name)
        from candidates.story_vector_cache import model_identity
        self.cache_identity = model_identity(files, ort.__version__)
        options=ort.SessionOptions()
        options.intra_op_num_threads=2
        options.inter_op_num_threads=1
        self.session=ort.InferenceSession(str(directory/next(iter(files))),sess_options=options,
                                         providers=["CPUExecutionProvider"])
        self.tokenizer=Tokenizer.from_file(str(directory/"onnx/tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=512)
        self.tokenizer.enable_padding(pad_id=self.tokenizer.token_to_id("<pad>") or 0, pad_token="<pad>")
        self.cache=OrderedDict()
        self.lock=RLock()

    def encode(self,texts,prefix="passage: ",cancelled=None):
        np=self.np
        keys=[prefix+t for t in texts]
        if not keys: return np.empty((0,384),dtype=np.float32)
        with self.lock:
            missing=list(dict.fromkeys(k for k in keys if k not in self.cache))
            for offset in range(0,len(missing),16):
                if cancelled is not None and cancelled():
                    raise InterruptedError("Story indexing cancelled")
                batch=missing[offset:offset+16]
                enc=self.tokenizer.encode_batch(batch)
                data={"input_ids":np.array([e.ids for e in enc],dtype=np.int64),
                      "attention_mask":np.array([e.attention_mask for e in enc],dtype=np.int64),
                      "token_type_ids":np.array([e.type_ids for e in enc],dtype=np.int64)}
                output=self.session.run(None,{i.name:data[i.name] for i in self.session.get_inputs()})[0]
                mask=data["attention_mask"][...,None]
                pooled=(output*mask).sum(axis=1)/np.maximum(mask.sum(axis=1),1)
                pooled=pooled/np.maximum(np.linalg.norm(pooled,axis=1,keepdims=True),1e-12)
                for key,vector in zip(batch,pooled):self.cache[key]=vector.astype(np.float32)
            result=np.stack([self.cache[k] for k in keys])
            # Bounded in-memory cache; no persistence of queries or personal library.
            while len(self.cache)>4096:self.cache.popitem(last=False)
            if prefix == "query: ":
                for key in keys: self.cache.pop(key, None)
            return result


def normalized_query(query, vocabulary):
    """Use document vocabulary for conservative typo repair; preserve normal words.

    The role lexicon supplies inflected query forms when a synonym-only corpus
    lacks the literal word. This is soft query normalization, never a gate.
    """
    from difflib import SequenceMatcher
    vocabulary=set(vocabulary)|{w for forms in ROLE_WORDS.values() for w in forms}
    vocabulary|={"преступника","следователя","преступник"}
    words=tokens(query)
    fixed=[]
    for word in words:
        if word in vocabulary or word in STOP or len(word)<7:
            fixed.append(word);continue
        near=[v for v in vocabulary if abs(len(v)-len(word))<=2 and v[:2]==word[:2]]
        score,best=max(((SequenceMatcher(None,word,v).ratio(),v) for v in near),default=(0,word))
        fixed.append(best if score>=.8 else word)
    return " ".join(fixed)


class SemanticStorySearch:
    def __init__(self,documents,encoder,*,cancelled=None):
        self.documents=tuple(documents)
        self.title_words={tuple(tokens(d.title)) for d in self.documents}
        self.encoder=encoder
        self.vocabulary={w for d in documents for w in tokens(d.overview)}
        self.vectors=encoder.encode([d.overview for d in self.documents], **({"cancelled": cancelled} if cancelled else {}))
        self.lexical=LexicalIndex(self.documents)

    def _response(self, hits, notice):
        return StoryResponse(hits, notice, "E5 small · локальный гибрид · " + self.encoder.variant)

    def search(self,query,*,excluded=frozenset(),limit=5,rerank=False,hybrid=True,domain_filters=True,repair_typos=True,evidence=True,role_adjustment=False):
        words=tokens(query)
        if len(query)>600:return self._response((),"Сократите описание до 600 символов.")
        if not(set(words)-STOP):return self._response((),"Опишите героя или событие.")
        if unsupported_negation(query):
            return self._response((),"Отрицания пока не поддерживаются. Опишите желаемую историю утвердительно.")
        if domain_filters and instructional_non_plot(query, self.title_words):
            return self._response((), OUT_OF_SCOPE_NOTICE)
        kind,year=media_constraints(query) if domain_filters else (None,None)
        indices=[i for i,d in enumerate(self.documents) if d.key not in excluded and (not kind or d.media_type==kind) and (year is None or d.year==year)]
        if not indices:return self._response((),"В этом локальном наборе пока нет подходящих описаний.")
        corrected=normalized_query(query,self.vocabulary) if repair_typos else query
        q=self.encoder.encode([corrected],prefix="query: ")[0]
        dense={i:float(self.vectors[i]@q) for i in indices}
        text_scores=self.lexical.scores(corrected)
        lexical={i:text_scores[i] for i in indices}
        dense_order=sorted(indices,key=lambda i:(-dense[i],self.documents[i].key))
        lexical_order=sorted((i for i in indices if lexical[i]>0),key=lambda i:(-lexical[i],self.documents[i].key))
        # Union recall: semantic candidates survive even with zero literal overlap.
        candidates=set(dense_order[:40])|set(lexical_order[:40])
        dense_rank={i:r for r,i in enumerate(dense_order)}
        lexical_rank={i:r for r,i in enumerate(lexical_order)}
        rrf={i:1/(60+dense_rank[i])+(0.35/(60+lexical_rank[i]) if i in lexical_rank else 0) for i in candidates}
        ordered=sorted(candidates,key=lambda i:(-rrf[i],self.documents[i].key))
        requested_role=requested_protagonist(corrected)
        hits=[]
        for i in ordered:
            doc=self.documents[i]
            sentences=[s.strip() for s in re.split(r"(?<=[.!?])\s+",doc.overview) if s.strip()]
            if not sentences:continue
            similarity=(self.encoder.encode(sentences)@q) if rerank else None
            best=int(similarity.argmax()) if similarity is not None else 0
            excerpt=sentences[best]
            score=rrf[i] if hybrid else dense[i]
            if hybrid and role_adjustment and requested_role:
                role = protagonist(doc.overview)
                if role:
                    # Small bounded adjustment preserves both retrieval signals.
                    # No inference of a protagonist from mere topic overlap.
                    score *= 1.1 if role == requested_role else .9
            if rerank:
                # Separate measurable plot fit: full synopsis, lead protagonist
                # context, best evidence sentence. Role heuristic is only a small
                # soft bonus/penalty; it cannot remove semantic candidates.
                score=.65*dense[i]+.25*float(similarity[0])+.10*float(similarity[best])
                role=protagonist(doc.overview)
                if requested_role and role:
                    score+=.02 if requested_role==role else -.02
            hits.append(StoryHit(doc,float(score),excerpt))
        hits.sort(key=lambda h:(-h.score,h.document.key))
        final_hits = hits[:max(0,min(limit,10))]
        if evidence and not rerank:
            # Explain only the final cards. Extraction never changes their order.
            explained = []
            for hit in final_hits:
                sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", hit.document.overview) if s.strip()]
                best = int((self.encoder.encode(sentences) @ q).argmax())
                explained.append(StoryHit(hit.document, hit.score, sentences[best]))
            final_hits = explained
        return self._response(tuple(final_hits),
            "Возможные совпадения из локального набора. Проверьте сюжет по описанию.")

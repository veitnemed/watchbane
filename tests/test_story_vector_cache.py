from hashlib import sha256
from pathlib import Path
import pytest
np = pytest.importorskip("numpy")
from candidates.story_vector_cache import PassageVectorCache, CachedPassageEncoder, MAGIC, RECORD_SIZE


class Encoder:
    np = np
    variant = 'test'
    cache_identity = 'model-a/tokenizer-a/runtime-a'
    def __init__(self): self.calls = []
    def encode(self, texts, prefix='passage: ', **kwargs):
        self.calls.append((list(texts), prefix))
        rows = []
        for text in texts:
            v = np.zeros(384, dtype=np.float32)
            v[int(sha256(text.encode()).hexdigest()[:4],16) % 384] = 1
            rows.append(v)
        return np.stack(rows) if rows else np.empty((0,384),dtype=np.float32)


def test_restart_reuses_exact_vectors_and_only_changed_text_misses(tmp_path):
    first = CachedPassageEncoder(Encoder(),tmp_path)
    expected = first.encode(['один','два','один'])
    restarted = CachedPassageEncoder(Encoder(),tmp_path)
    assert np.array_equal(restarted.encode(['один','два','один']),expected)
    assert not restarted.encoder.calls
    restarted.encode(['один','новое описание'])
    assert restarted.encoder.calls == [(['новое описание'],'passage: ')]
    assert restarted.cache.writes == 1


def test_model_preprocessing_and_profile_are_isolated(tmp_path):
    enc = Encoder(); vector = enc.encode(['text'])[0]
    a = PassageVectorCache(tmp_path/'a', 'model-one', 'prep-one'); a.save('text',vector)
    for cache in (PassageVectorCache(tmp_path/'a','model-two','prep-one'),
                  PassageVectorCache(tmp_path/'a','model-one','prep-two'),
                  PassageVectorCache(tmp_path/'b','model-one','prep-one')):
        assert cache.load('text') is None
    b = PassageVectorCache(tmp_path/'a','model-two','prep-one')
    b.root.mkdir(parents=True); b.path('text').write_bytes(a.path('text').read_bytes())
    assert b.load('text') is None  # a copied other-model record is also rejected


@pytest.mark.parametrize('damage',['truncated','oversize','checksum','nan','wrong_text'])
def test_corrupt_record_recomputed_without_loading_executable_data(tmp_path,damage):
    cached=CachedPassageEncoder(Encoder(),tmp_path); expected=cached.encode(['one'])[0]
    path=cached.cache.path('one'); raw=path.read_bytes()
    if damage=='truncated': raw=raw[:12]
    elif damage=='oversize': raw=raw+b'x'
    elif damage=='checksum': raw=raw[:-1]+bytes([raw[-1]^1])
    elif damage=='wrong_text': raw=raw[:8]+b'x'*32+raw[40:]
    else:
        vector=np.full(384,np.nan,dtype='<f4').tobytes()
        raw=raw[:40]+vector;raw+=sha256(raw).digest()
    path.write_bytes(raw)
    fresh=CachedPassageEncoder(Encoder(),tmp_path)
    assert np.array_equal(fresh.encode(['one'])[0],expected)
    assert fresh.encoder.calls == [(['one'],'passage: ')]
    assert fresh.cache.errors==1
    assert fresh.cache.load('one') is not None


def test_atomic_failure_keeps_old_record_and_removes_temp(tmp_path,monkeypatch):
    cache=PassageVectorCache(tmp_path,'model'); v=Encoder().encode(['one'])[0]
    cache.save('one',v); before=cache.path('one').read_bytes()
    import candidates.story_vector_cache as module
    monkeypatch.setattr(module.os,'replace',lambda *a: (_ for _ in ()).throw(OSError('interrupted replace')))
    cache.save('one',v)
    assert cache.path('one').read_bytes()==before
    assert not list(cache.root.glob('*.tmp'))
    assert cache.load('one') is not None


def test_query_never_persisted_and_disk_failure_is_optional(tmp_path,monkeypatch):
    cached=CachedPassageEncoder(Encoder(),tmp_path)
    cached.encode(['private query'],prefix='query: ')
    assert not cached.cache.root.exists()
    monkeypatch.setattr(Path,'mkdir',lambda *a,**k: (_ for _ in ()).throw(PermissionError('read only')))
    assert cached.encode(['passage']).shape==(1,384)
    assert cached.cache.errors == 1


def test_cancelled_index_does_not_write(tmp_path):
    cached=CachedPassageEncoder(Encoder(),tmp_path)
    with pytest.raises(InterruptedError):cached.encode(['text'],cancelled=lambda:True)
    assert not cached.cache.root.exists() and not cached.encoder.calls


def test_concurrent_writes_are_complete_records(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    def write(_):
        cache=PassageVectorCache(tmp_path,'model'); cache.save('one',Encoder().encode(['one'])[0])
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(write,range(16)))
    cache=PassageVectorCache(tmp_path,'model')
    assert cache.load('one') is not None and cache.path('one').stat().st_size==RECORD_SIZE
    assert not list(cache.root.glob('*.tmp'))


def test_record_symlink_not_read(tmp_path):
    cache=PassageVectorCache(tmp_path,'model');v=Encoder().encode(['one'])[0];cache.save('one',v)
    outside=tmp_path/'outside';outside.write_bytes(cache.path('one').read_bytes())
    cache.path('one').unlink();cache.path('one').symlink_to(outside)
    assert cache.load('one') is None
    cache.save('one',v)
    assert not cache.path('one').is_symlink()
    assert outside.read_bytes()==cache.path('one').read_bytes()


def test_service_uses_active_profile_and_restart_cache(tmp_path,monkeypatch):
    from candidates import story_service as service
    from candidates.story_search import StoryDocument
    import storage.profiles as profiles
    active=[tmp_path/'profile-a']
    monkeypatch.setattr(profiles,'get_active_data_dir',lambda:active[0])
    encoders=[]
    def new_encoder(_):
        enc=Encoder();encoders.append(enc);return enc
    monkeypatch.setattr(service,'_local_encoder',new_encoder)
    docs=[StoryDocument('a','A','Врач лечит пациентов.','tv','synthetic')]
    service.clear_story_search_cache()
    first=service.create_story_search(docs,'fake-model')
    assert first.encoder.cache.writes==1
    service.clear_story_search_cache()
    second=service.create_story_search(docs,'fake-model')
    assert second.encoder.cache.hits==1 and not encoders[-1].calls
    active[0]=tmp_path/'profile-b'
    third=service.create_story_search(docs,'fake-model')
    assert third is not second and third.encoder.cache.misses==1
    assert (active[0]/'story_vectors_v1').is_dir()
    service.clear_story_search_cache()

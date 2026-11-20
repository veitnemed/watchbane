"""All TMDb responses here are original synthetic fixtures, never live data."""
import pytest
from candidates.story_catalog import fill_story_catalog
from candidates.repositories.pool_repository import load_candidate_pool


class FakeTMDb:
    def __init__(self, fail=False, on_detail=None):
        self.calls=[];self.fail=fail;self.on_detail=on_detail
    def discover(self,media,params):
        self.calls.append(('discover',media,dict(params)))
        return {'results':[{'id':101},{'id':102},{'id':103}], 'total_pages':1}
    def details(self,media,identifier,language):
        self.calls.append(('details',media,identifier,language))
        if self.on_detail:self.on_detail()
        if self.fail and media=='tv':raise OSError('mock offline')
        english=identifier==102
        return {'id':identifier,'title':f'Вымышленный фильм {identifier}', 'name':f'Вымышленный сериал {identifier}',
                'release_date':'2020-01-02','first_air_date':'2020-01-02','adult':False,
                'overview':('' if language=='ru-RU' else 'A fictional physician treats patients in a remote hospital.') if english else 'Врач лечит пациентов в далёкой больнице.',
                'genres':[{'id':18,'name':'Drama'}], 'vote_average':7.4,'vote_count':150,'popularity':20,
                'original_language':'en','runtime':100,'episode_run_time':[45],'number_of_seasons':1}


def test_official_adapter_import_and_english_fallback(monkeypatch):
    from apis import tmdb_api
    fake=FakeTMDb()
    monkeypatch.setattr(tmdb_api,'tmdb_get',lambda path,params,**kw:fake.discover(path.rsplit('/',1)[-1],params))
    monkeypatch.setattr(tmdb_api,'get_movie_details',lambda identifier,language,**kw:fake.details('movie',identifier,language))
    monkeypatch.setattr(tmdb_api,'get_tv_details',lambda identifier,language,**kw:fake.details('tv',identifier,language))
    result=fill_story_catalog()
    assert result['saved_count']==6 and result['english_fallback_count']==2
    from candidates.story_service import story_catalog_snapshot
    docs,_=story_catalog_snapshot()
    assert len(docs)==6 and sum('английский fallback' in d.source for d in docs)==2
    assert {d.media_type for d in docs}=={'movie','tv'}
    assert all('query' not in call[2] for call in fake.calls if call[0]=='discover')
    assert all(call[2]['language']=='ru-RU' and call[2]['page']==1 for call in fake.calls if call[0]=='discover')


def test_idempotent_repeat_preserves_saved_hidden_watched():
    from candidates.service import hide_candidate,add_candidate_to_watchlist,mark_story_watched
    from candidates.title_state_service import get_title_state
    fake=FakeTMDb();fill_story_catalog(client=fake)
    rows=list(load_candidate_pool().values())
    hide_candidate(rows[0]);add_candidate_to_watchlist(rows[1]);mark_story_watched(rows[2])
    states=[get_title_state(r) for r in rows]
    before=load_candidate_pool()
    repeated=fill_story_catalog(client=FakeTMDb())
    assert repeated['saved_count']==0
    assert load_candidate_pool()==before
    assert [get_title_state(r) for r in rows]==states


@pytest.mark.parametrize('cancel',[False,True])
def test_error_or_cancel_does_not_commit_partial_batch(cancel):
    fill_story_catalog(client=FakeTMDb())
    before=load_candidate_pool()
    # A second batch has different IDs, so it cannot short-circuit on duplicates.
    fake=FakeTMDb(fail=not cancel)
    fake.discover=lambda media,params:{'results':[{'id':201},{'id':202}]}
    stop=[False]
    if cancel:fake.on_detail=lambda:stop.__setitem__(0,True)
    if cancel:
        assert fill_story_catalog(client=fake,cancel_checker=lambda:stop[0])['cancelled']
    else:
        with pytest.raises(OSError):fill_story_catalog(client=fake)
    assert load_candidate_pool()==before


def test_bounded_import_and_missing_descriptions():
    fake=FakeTMDb();fake.discover=lambda media,params:{'results':[{'id':i} for i in range(1,1001)]}
    result=fill_story_catalog(client=fake)
    assert result['created_count']==30 and result['api_requests']<=62
    before=load_candidate_pool()
    empty=FakeTMDb();empty.details=lambda media,identifier,language:{'id':identifier,'overview':''}
    empty.discover=lambda media,params:{'results':[{'id':9999}]}
    assert fill_story_catalog(client=empty)['saved_count']==0
    assert load_candidate_pool()==before


def test_cancellation_immediately_before_import():
    fake=FakeTMDb(); stop=[False]
    def progress(update):
        if update.get('message','').startswith('Получено описаний: 6 '):stop[0]=True
    result=fill_story_catalog(client=fake,cancel_checker=lambda:stop[0],progress_callback=progress)
    assert result['cancelled'] and not load_candidate_pool()


def test_replenish_scans_pages_and_skips_existing_typed_ids_without_details():
    class PagedTMDb(FakeTMDb):
        def discover(self, media, params):
            self.calls.append(('discover', media, dict(params)))
            page = params['page']
            # One overlapping ID across successive pages, and identical IDs
            # across movie/TV. Neither may create duplicate work within a kind.
            start = 301 + 19 * (page - 1)
            return {'results': [{'id': n} for n in range(start, start + 20)],
                    'total_pages': 3}

    first = PagedTMDb()
    assert fill_story_catalog(client=first)['saved_count'] == 30
    second = PagedTMDb()
    assert fill_story_catalog(client=second)['saved_count'] == 30
    rows = list(load_candidate_pool().values())
    assert len(rows) == 60
    for media in ('movie', 'tv'):
        assert {r['tmdb_id'] for r in rows if r['media_type'] == media} == set(range(301, 331))
        assert [c[2]['page'] for c in second.calls if c[:2] == ('discover', media)] == [1, 2]
        assert [c[2] for c in second.calls if c[:2] == ('details', media)] == list(range(316, 331))


def test_replenish_page_limit_on_duplicate_only_responses():
    from candidates.story_catalog import MAX_DISCOVER_PAGES

    class RepeatingTMDb(FakeTMDb):
        def discover(self, media, params):
            self.calls.append(('discover', media, dict(params)))
            return {'results': [{'id': 101}] * 20, 'total_pages': 500}

    fake = RepeatingTMDb()
    assert fill_story_catalog(client=fake)['saved_count'] == 2
    better = RepeatingTMDb()
    assert fill_story_catalog(client=better)['saved_count'] == 0
    assert len(better.calls) == 2 * MAX_DISCOVER_PAGES
    assert all(c[0] == 'discover' for c in better.calls)

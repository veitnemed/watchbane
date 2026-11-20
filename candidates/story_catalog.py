"""Explicit bounded TMDb acquisition for story search; never receives a query."""
from candidates.repositories.pool_repository import load_candidate_pool
from candidates.safety.explicit_content import is_blocked_explicit_sexual_content
from candidates.sources.tmdb.normalizer import prepare_tmdb_candidate, prepare_tmdb_movie_candidate
from candidates.sources.tmdb.importer import import_story_catalog_candidates

PER_MEDIA_LIMIT = 15
MAX_DISCOVER_PAGES = 10
DISCOVER_PAGE_SIZE = 20


def fill_story_catalog(*, client=None, progress_callback=None, cancel_checker=None, dry_run=False):
    from candidates.onboarding_service import _build_filter_replenish_tmdb_client
    client = client or _build_filter_replenish_tmdb_client()
    cancelled = lambda: bool(cancel_checker and cancel_checker())
    before = load_candidate_pool()
    existing = {(r.get('media_type'),r.get('tmdb_id')) for r in before.values()}
    selected=[]; requests=0; skipped=0; english=0
    def stop():
        return {'ok':False,'cancelled':True,'saved_count':0,'created_count':0,'api_requests':requests}
    for media in ('movie','tv'):
        if cancelled():return stop()
        if progress_callback:progress_callback({'message':'Загружаем фильмы…' if media=='movie' else 'Загружаем сериалы…'})
        seen = set()
        media_count = 0
        for page in range(1, MAX_DISCOVER_PAGES + 1):
            if cancelled():return stop()
            response = client.discover(media, {
                'page': page, 'language': 'ru-RU', 'include_adult': False,
                'sort_by': 'popularity.desc',
            })
            requests += 1
            if cancelled():return stop()
            if not isinstance(response, dict) or not isinstance(response.get('results'), list):
                raise ValueError('Invalid discover response')
            rows = response['results']
            for row in rows[:DISCOVER_PAGE_SIZE]:
                if cancelled():return stop()
                identifier=row.get('id') if isinstance(row,dict) else None
                if not isinstance(identifier,int) or isinstance(identifier,bool) or identifier<=0:continue
                if (media,identifier) in existing or identifier in seen:
                    skipped+=1;continue
                seen.add(identifier)
                details=client.details(media,identifier,language='ru-RU');requests+=1
                if cancelled():return stop()
                if not isinstance(details,dict) or details.get('id')!=identifier:raise ValueError('Invalid details response')
                language='ru-RU'
                # Use an explicitly requested locale, never invent a translation.
                if not str(details.get('overview') or '').strip():
                    details=client.details(media,identifier,language='en-US');requests+=1;language='en-US'
                    if cancelled():return stop()
                    if not isinstance(details,dict) or details.get('id')!=identifier:raise ValueError('Invalid fallback response')
                if not str(details.get('overview') or '').strip():continue
                normalizer=prepare_tmdb_movie_candidate if media=='movie' else prepare_tmdb_candidate
                candidate=normalizer(details,source_query={'language':language,'acquisition':'story_catalog'})
                if not candidate.get('title') or not candidate.get('year') or is_blocked_explicit_sexual_content(candidate):continue
                selected.append(candidate)
                media_count += 1
                english+=language=='en-US'
                if progress_callback:progress_callback({'message':f'Получено описаний: {len(selected)} из максимум 30.'})
                if media_count == PER_MEDIA_LIMIT:
                    break
            last = response.get('total_pages')
            known_last = type(last) is int and last >= 0
            if (media_count == PER_MEDIA_LIMIT or not rows
                    or (known_last and page >= last)
                    or (not known_last and len(rows) < DISCOVER_PAGE_SIZE)):
                break
    if cancelled():return stop()
    result={'ok':True,'cancelled':False,'created_count':len(selected),'saved_count':0,'api_requests':requests,
            'english_fallback_count':english,'existing_skipped':skipped}
    if selected and not dry_run:
        # Explicit Story import only upserts exact typed identities into the existing pool.
        stats=import_story_catalog_candidates(selected,
                 result_metadata={'source':'story_catalog','language':'ru-RU','english_fallback_count':english})
        result.update(saved_count=stats.get('added',0),save_stats=stats)
    return result


class StoryCatalogImportService:
    """Adapter for the existing cancelable FilterReplenishWorker protocol."""
    @staticmethod
    def replenish_candidate_pool_for_filters(_intent, **kwargs):
        return fill_story_catalog(**kwargs)

"""Print a small candidate search result from the local pool."""

from app.use_cases.candidate_search import load_candidate_search_screen


result = load_candidate_search_screen(
    filters={"media_type": "tv", "min_year": 2010},
    text_query="dark thriller",
)

for item in result["candidates"][:10]:
    print(item.get("title"), item.get("final_score"))

import logging
import re
from icecream import ic
from azure.monitor.opentelemetry import configure_azure_monitor
from app.shared.env import *

if APPINSIGHTS_CONNECTION_STRING:
    configure_azure_monitor(
        connection_string=APPINSIGHTS_CONNECTION_STRING, 
        logger_name=APP_NAME, 
        instrumentation_options={"fastapi": {"enabled": True}})  
logger: logging.Logger = logging.getLogger(APP_NAME)
logger.setLevel(logging.INFO)

from app.pybeansack.mongosack import Beansack, NEWEST_AND_TRENDING
from app.pybeansack.models import *

BEAN_FIELDS = {K_URL: 1, K_TITLE: 1, "gist": 1, "categories": 1, "entities": 1, K_SUMMARY: 1, K_KIND: 1, K_IMAGEURL: 1, K_AUTHOR: 1, K_SOURCE: 1, K_CREATED: 1}
db: Beansack = None

def get_all_sources():
    return sorted(db.beanstore.distinct(K_SOURCE))

def get_all_tags():
    return db.beanstore.distinct(K_TAGS)

def query_beans(
    kind: str, 
    entities: str|list[str]|list[list[str]], 
    categories: str|list[str], 
    sources: str|list[str], 
    published_after: datetime, 
    start: int, 
    limit: int
) -> list[Bean]:
    filter=create_filter(
        kind=kind,
        entities=entities, 
        categories=categories, 
        sources=sources, 
        published_after=published_after
    )
    return db.get_beans(filter=filter, sort_by=NEWEST_AND_TRENDING, skip=start, limit=limit, projection=BEAN_FIELDS)

def query_distinct_beans_per_cluster(
    kind: str, 
    entities: str|list[str]|list[list[str]], 
    categories: str|list[str], 
    sources: str|list[str], 
    published_after: datetime, 
    start: int, 
    limit: int
):
    filter=create_filter(
        kind=kind,
        entities=entities, 
        categories=categories, 
        sources=sources, 
        published_after=published_after
    )
    return db.query_beans_per_cluster(filter, NEWEST_AND_TRENDING, start, limit, projection=BEAN_FIELDS)

def search_distinct_beans_per_cluster(
    query: str,
    min_score: float,
    kind: str, 
    entities: str|list[str]|list[list[str]], 
    categories: str|list[str], 
    sources: str|list[str], 
    published_after: datetime, 
    start: int, 
    limit: int
):
    filter=create_filter(
        kind=kind,
        entities=entities, 
        categories=categories, 
        sources=sources, 
        published_after=published_after
    )
    # db.vector_search_beans(nlp.)

def create_filter(
    kind: str,
    entities: str|list[str]|list[list[str]], 
    categories: str|list[str], 
    sources: str|list[str],
    published_after: int
) -> dict:   
    filter = {}
    if kind: filter[K_KIND] = lower_case(kind)
    if entities: filter[K_TAGS] = case_insensitive(entities)  
    if categories: filter["categories"] = case_insensitive(entities)
    if sources: filter[K_SOURCE] = case_insensitive(sources)
    if published_after: filter[K_CREATED] = {"$gte": published_after}
    return filter

field_value = lambda items: {"$in": items} if isinstance(items, list) else items
lower_case = lambda items: {"$in": [item.lower() for item in items]} if isinstance(items, list) else items.lower()
case_insensitive = lambda items: {"$in": [re.compile(item, re.IGNORECASE) for item in items]} if isinstance(items, list) else re.compile(items, re.IGNORECASE)


import uvicorn
from fastapi import FastAPI, Query
from app.shared import beanops, utils, messages

router = FastAPI(title=APP_NAME, version="0.0.1", description="API for Espresso (Alpha)")

def initialize_server():
    global db
    db = Beansack(DB_CONNECTION_STRING, DB_NAME)
    logger.info("server_initialized")

@router.get("/sources", response_model=list[str]|None)
async def get_sources() -> list[str]:
    return beanops.get_all_sources()

@router.get("/categories", response_model=list[str]|None)
async def get_categories() -> list[str]:
    return beanops.get_all_categories()

@router.get("/entities", response_model=list[str]|None)
async def get_entities() -> list[str]:
    return beanops.get_all_entities()

@router.get("/{kind}", response_model=list[Bean]|None)
async def get_beans(
    kind: str,
    q: str = Query(),
    acc: float = Query(),
    categories: list[str] = Query(),
    entities: list[str] = Query(),
    sources: list[str] = Query(),
    published_after: str = Query()
) -> list[Bean]:
    if q: return beanops.search_beans(q, acc, entities, kind, sources, DEFAULT_WINDOW, "Latest", 0, MAX_LIMIT)
    else: return beanops.get_beans(None, entities, kind, sources, DEFAULT_WINDOW, "Latest", 0, MAX_LIMIT)

@router.get("/{kind}/markdown")
async def get_beans_markdown(
    kind: str,
    q: str = Query(default=None),
    acc: float = Query(default=DEFAULT_ACCURACY),
    categories: list[str] = Query(default=None),
    entities: list[str] = Query(default=None),
    sources: list[str] = Query(default=None),
    published_after: str = Query(default=None)
):
    if q: beans = beanops.search_beans(q, acc, entities, kind, sources, MAX_WINDOW, "Latest", 0, MAX_LIMIT)
    else: beans = beanops.get_beans(None, entities, kind, sources, MAX_WINDOW, "Latest", 0, MAX_LIMIT)
    markdown = "\n\n".join([bean.digest() for bean in beans])
    # for bean in beans:
    #     markdown += bean.digest()+"\n\n"
    #     related = beanops.get_related(bean.url, bean.tags, None, None, MAX_WINDOW, 4)
    #     if related:
    #         markdown += f"## Related {kind}:\n"
    #         markdown += "\n\n".join("##"+r.digest() for r in related)
    #     markdown += "\n--------------------------------\n"
    return markdown

@router.get("/beans", response_model=list[Bean]|None)
async def get_beans(
    url: list[str] | None = Query(max_length=MAX_LIMIT, default=None),
    tag: list[str] | None = Query(max_length=MAX_LIMIT, default=None),
    kind: list[str] | None = Query(max_length=MAX_LIMIT, default=None), 
    source: list[str] = Query(max_length=MAX_LIMIT, default=None),
    ndays: int | None = Query(ge=MIN_WINDOW, le=MAX_WINDOW, default=None), 
    start: int | None = Query(ge=0, default=0), 
    limit: int | None = Query(ge=MIN_LIMIT, le=MAX_LIMIT, default=MAX_LIMIT)):
    """
    Retrieves the bean(s) with the given URL(s).
    """
    res = get_beans(url, tag, kind, source, ndays, start, limit)  
    log('get_beans', url=url, tag=tag, kind=kind, source=source, ndays=ndays, start=start, limit=limit, num_returned=res)
    return res

@router.get("/search", response_model=list[Bean]|None)
async def search_beans(
    q: str, 
    acc: float = Query(ge=0, le=1, default=DEFAULT_ACCURACY),
    tag: list[str] | None = Query(max_length=MAX_LIMIT, default=None),
    kind: list[str] | None = Query(max_length=MAX_LIMIT, default=None), 
    source: list[str] = Query(max_length=MAX_LIMIT, default=None),
    ndays: int | None = Query(ge=MIN_WINDOW, le=MAX_WINDOW, default=None), 
    start: int | None = Query(ge=0, default=0), 
    limit: int | None = Query(ge=MIN_LIMIT, le=MAX_LIMIT, default=DEFAULT_LIMIT)):
    """
    Search beans by various parameters.
    q: query string
    acc: accuracy
    tags: list of tags
    kinds: list of kinds
    source: list of sources
    ndays: last n days
    start: start index
    limit: limit
    """
    res = vector_search_beans(q, acc, tag, kind, source, ndays, start, limit)
    log('search_beans', q=q, acc=acc, tag=tag, kind=kind, source=source, ndays=ndays, start=start, limit=limit, num_returned=res)
    return res

@router.get("/trending", response_model=list[Bean]|None)
async def trending_beans(
    tag: list[str] | None = Query(max_length=MAX_LIMIT, default=None),
    kind: list[str] | None = Query(default=None), 
    source: list[str] = Query(max_length=MAX_LIMIT, default=None),
    ndays: int | None = Query(ge=MIN_WINDOW, le=MAX_WINDOW, default=None), 
    start: int | None = Query(ge=0, default=0), 
    limit: int | None = Query(ge=MIN_LIMIT, le=MAX_LIMIT, default=MAX_LIMIT)):
    """
    Retuns a set of unique beans, meaning only one bean from each cluster will be included in the result.
    To retrieve all the beans irrespective of cluster, use /beans endpoint.
    To retrieve the beans related to the beans in this result set, use /beans/related endpoint.
    """
    res = get_trending_beans(tag, kind, source, ndays, start, limit)
    log('trending_beans', tag=tag, kind=kind, source=source, ndays=ndays, start=start, limit=limit, num_returned=res)
    return res

@router.get("/related", response_model=list[Bean]|None)
async def get_related(
    url: str, 
    tag: list[str] | None = Query(max_length=MAX_LIMIT, default=None),
    kind: list[str] | None = Query(default=None), 
    source: list[str] = Query(max_length=MAX_LIMIT, default=None),
    ndays: int | None = Query(ge=MIN_WINDOW, le=MAX_WINDOW, default=None), 
    start: int | None = Query(ge=0, default=0), 
    limit: int | None = Query(ge=MIN_LIMIT, le=MAX_LIMIT, default=MAX_LIMIT)):
    """
    Retrieves the related beans to the given bean.
    """    
    res = get_related(url, tag, kind, source, ndays, start, limit)
    log('get_related_beans', url=url, tag=tag, kind=kind, source=source, ndays=ndays, start=start, limit=limit, num_returned=res)
    return res


# @app.get("/chatters", response_model=list[Chatter]|None)
# async def get_chatters(url: list[str] | None = Query(max_length=MAX_LIMIT, default=None)):
#     """
#     Retrieves the latest social media stats for the given bean(s).
#     """
#     res = shared.beanops.get_chatters(url)
#     log(logger, 'get_chatters', url=url, num_returned=res)
#     return res

# @app.get("/sources/all", response_model=list|None)
# async def get_sources():
#     """
#     Retrieves the list of sources.
#     """
#     res = get_all_sources()
#     log('get_sources', num_returned=res)
#     return res

# @app.get("/tags/all", response_model=list|None)
# async def get_tags():
#     """
#     Retrieves the list of tags.
#     """
#     res = get_all_tags()
#     log('get_tags', num_returned=res)
#     return res

# initialize_server()



def run():
    initialize_server()
    uvicorn.run(router, host="0.0.0.0", port=8080)


import logging
import uvicorn
from fastapi import FastAPI, Path, Query
from typing import Literal

from pybeansack.mongosack import NEWEST
from pybeansack.models import *
from app.shared.env import *
from app.shared.utils import *
from app.shared.consts import *

logger: logging.Logger = logging.getLogger(config.app.name)
logger.setLevel(logging.INFO)

FIELDS_WITH_CONTENT = {
    K_ID: 0, 
    K_COLLECTED: 0, K_UPDATED: 0,  
    K_TRENDSCORE: 0, 
    K_TAGS: 0, K_GIST: 0, 
    K_EMBEDDING: 0, K_CLUSTER_ID: 0, 
    "is_scraped": 0, 
    K_SITE_RSS_FEED: 0, K_SITE_FAVICON: 0, K_SITE_BASE_URL: 0 
}
FIELDS_WITHOUT_CONTENT = {**FIELDS_WITH_CONTENT, **{K_CONTENT: 0}}

create_projection = lambda with_content: FIELDS_WITH_CONTENT if with_content else FIELDS_WITHOUT_CONTENT
convert_kind = lambda val: BLOG if val == "blogs" else NEWS

def create_filter(
    kind: str,
    categories: str|list[str], 
    entities: str|list[str], 
    regions: str|list[str],
    sources: str|list[str],
    published_after: datetime,
    with_content: bool
) -> dict:   
    # pre process since they will all go to the tags filter
    tags = []
    if categories: tags.append({K_TAGS: lower_case(categories)})
    if entities: tags.append({K_TAGS: lower_case(entities)})
    if regions: tags.append({K_TAGS: lower_case(regions)})

    filter = {}
    if kind: filter[K_KIND] = convert_kind(lower_case(kind))
    if tags: filter["$and"] = tags
    if sources: filter[K_SOURCE] = lower_case(sources)
    if published_after: filter[K_CREATED] = {"$gte": published_after}
    if with_content: filter.update({
        K_CONTENT: {"$exists": True},
        '$or': [
            {'is_scraped': False},
            {'is_scraped': {"$exists": False}}
        ]
    })
    
    return filter

Q = Query(..., min_length=3)
SEARCH_TYPE = Query(default = "vector", description="Indicate if the search should be a semantic (vector) search or a text keyword (bm25) search")   
SIMILARITY_SCORE = Query(default=config.filters.bean.default_accuracy, description="Minimum cosine similarity score (only applicable to vector search)")
URL = Query(..., min_length="10")
QUERY_KIND = Query(default=None)
CATEGORIES = Query(max_length=MAX_LIMIT, default=None)
ENTITIES = Query(max_length=MAX_LIMIT, default=None)
REGIONS = Query(max_length=MAX_LIMIT, default=None)
SOURCES = Query(max_length=MAX_LIMIT, default=None)
PUBLISHED_AFTER = Query(default=None)
WITH_CONTENT = Query(default=False)
GROUP_BY = Query(default=None, description="[Optional] Return one item per `source`, `author` or `cluster` (news and blogs about the same items are groped in one cluster).")
OFFSET = Query(ge=0, default=0)
LIMIT = Query(ge=MIN_LIMIT, le=MAX_LIMIT, default=config.filters.bean.default_limit)

api_router = FastAPI(title=config.app.name, version="0.0.1", description=config.app.description)

@api_router.get("/sources", response_model=list[str]|None)
async def get_sources() -> list[str]:
    return db.beanstore.distinct("source")

@api_router.get("/categories", response_model=list[str]|None)
async def get_categories() -> list[str]:
    return db.beanstore.distinct("categories")

@api_router.get("/entities", response_model=list[str]|None)
async def get_entities() -> list[str]:
    return db.beanstore.distinct("entities")

@api_router.get("/regions", response_model=list[str]|None)
async def get_regions() -> list[str]:
    return db.beanstore.distinct("regions")

@api_router.get("/new/{kind}", response_model=list[Bean]|None)
async def get_beans(
    kind: Literal["news", "blogs"] = Path(),
    categories: list[str] = CATEGORIES,
    entities: list[str] = ENTITIES,
    regions: list[str] = REGIONS,
    sources: list[str] = SOURCES,
    published_after: datetime = PUBLISHED_AFTER,
    with_content: bool = WITH_CONTENT,
    group_by: Literal["cluster_id", "source", "author", None] = GROUP_BY,
    offset: int = OFFSET,
    limit: int = LIMIT
) -> list[Bean]:
    filter = create_filter(kind, categories, entities, regions, sources, published_after, with_content)
    project = create_projection(with_content) 
    return db.query_beans(filter=filter, group_by=group_by, sort_by=NEWEST, skip=offset, limit=limit, project=project)

@api_router.get("/search", response_model=list[Bean]|None)
async def search_beans(
    q: str = Q,
    search_type: Literal["vector", "bm25"] = SEARCH_TYPE,    
    similarity_score: float = SIMILARITY_SCORE,
    kind: Literal["news", "blogs", None] = QUERY_KIND,
    categories: list[str] = CATEGORIES,
    entities: list[str] = ENTITIES,
    regions: list[str] = REGIONS,
    sources: list[str] = SOURCES,
    published_after: datetime = PUBLISHED_AFTER,
    with_content: bool = WITH_CONTENT,
    group_by: Literal["cluster_id", "source", "author", None] = GROUP_BY,
    offset: int = OFFSET,
    limit: int = LIMIT
) -> list[Bean]:
    filter = create_filter(kind, categories, entities, regions, sources, published_after, with_content)
    project = create_projection(with_content) 
    if search_type == "vector": return db.vector_search_beans(embedding=embedder.embed_query(q), similarity_score=similarity_score, filter=filter, group_by=group_by, skip=offset, limit=limit, project=project)
    if search_type == "bm25": return db.text_search_beans(query=q, filter=filter, group_by=group_by, skip=offset, limit=limit, project=project)

@api_router.get("/related", response_model=list[Bean]|None)
async def get_related(
    url: str = Query(),
    kind: Literal["news", "blogs", None] = QUERY_KIND,
    categories: list[str] = CATEGORIES,
    entities: list[str] = ENTITIES,
    regions: list[str] = REGIONS,
    sources: list[str] = SOURCES,
    published_after: datetime = PUBLISHED_AFTER,
    with_content: bool = WITH_CONTENT,
    limit: int = LIMIT
) -> list[Bean]:
    """
    Retrieves the related beans to the given bean.
    """  
    filter = create_filter(kind, categories, entities, regions, sources, published_after, with_content)
    project = create_projection(with_content) 
    return db.query_related_beans(url, filter=filter, sort_by=NEWEST, limit=limit, project = project)

def run():
    uvicorn.run(api_router, host="0.0.0.0", port=8080)


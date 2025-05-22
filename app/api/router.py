import logging
from fastapi.responses import FileResponse
import uvicorn
from fastapi import FastAPI, Path, Query
from fastapi.staticfiles import StaticFiles
from typing import Literal

from pybeansack.mongosack import NEWEST
from pybeansack.models import *
from app.shared.env import *
from app.shared.utils import *
from app.shared.consts import *

logger: logging.Logger = logging.getLogger(config.app.name)
logger.setLevel(logging.INFO)

### BEANSACK RELATED FILTERING ####

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

### QUERY PARAMETER DEFINITIONS ###

Q = Query(
    ..., 
    min_length=3, 
    description="The search query string. Minimum length is 3 characters."
)
SEARCH_TYPE = Query(
    default="vector", 
    description="Indicate if the search should be a semantic (vector) search or a text keyword (bm25) search."
)
SIMILARITY_SCORE = Query(
    default=config.filters.bean.default_accuracy, 
    description="Minimum cosine similarity score (only applicable to vector search)."
)
URL = Query(
    ..., 
    min_length=10, 
    description="The URL of the bean for which related beans are to be found. Minimum length is 10 characters."
)
KIND = Query(
    default=None, 
    description="Type of bean to query: 'news', 'blogs', or keep it unspecified for both."
)
CATEGORIES = Query(
    max_length=MAX_LIMIT, 
    default=None, 
    description="One or more categories to filter beans."
)
ENTITIES = Query(
    max_length=MAX_LIMIT, 
    default=None, 
    description="One or more named entities to filter beans."
)
REGIONS = Query(
    max_length=MAX_LIMIT, 
    default=None, 
    description="One or more regions to filter beans."
)
SOURCES = Query(
    max_length=MAX_LIMIT, 
    default=None, 
    description="One or more source ids to filter beans."
)
PUBLISHED_AFTER = Query(
    default=None, 
    description="Only return beans published on or after this datetime."
)
WITH_CONTENT = Query(
    default=False, 
    description="Whether to include only beans with content."
)
GROUP_BY = Query(
    default=None, 
    description="Return one item per `source`, `author` or `cluster` (news and blogs about the same content are grouped in one cluster)."
)
OFFSET = Query(
    ge=0, 
    default=0, 
    description="Number of items to skip (for pagination)."
)
LIMIT = Query(
    ge=MIN_LIMIT, 
    le=MAX_LIMIT, 
    default=config.filters.bean.default_limit, 
    description="Maximum number of items to return."
)

### ROUTER AND ROUTE DEFINITIONS ###

api_router = FastAPI(title=config.app.name, version="0.0.1", description=config.app.description)
api_router.mount("/docs", StaticFiles(directory="docs"), "docs")

@api_router.get("/favicon.ico")
async def get_favicon():
    return FileResponse("./images/favicon.ico")

@api_router.get(
    "/sources", 
    response_model=list[str]|None,
    description="Get a list of all unique source ids available in the beansack."
)
async def get_sources() -> list[str]:
    return db.beanstore.distinct("source")

@api_router.get(
    "/categories", 
    response_model=list[str]|None,
    description="Get a list of all unique categories (e.g. AI, Cybersecurity, Politics, Software Engineering) available in the beansack."
)
async def get_categories() -> list[str]:
    return db.beanstore.distinct("categories")

@api_router.get(
    "/entities", 
    response_model=list[str]|None,
    description="Get a list of all unique named entities available in the beansack."
)
async def get_entities() -> list[str]:
    return db.beanstore.distinct("entities")

@api_router.get(
    "/regions", 
    response_model=list[str]|None,
    description="Get a list of all unique geographic regions available in the beansack."
)
async def get_regions() -> list[str]:
    return db.beanstore.distinct("regions")

@api_router.get(
    "/new/{kind}", 
    response_model=list[Bean]|None,
    response_model_by_alias=True,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
    description="Get a list of new beans (news or blogs) filtered by the provided parameters. The result is sorted by newest first."
)
async def get_beans(
    kind: Literal["news", "blogs"] = Path(description="Type of beans to retrieve: `news` or `blogs`."),
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

@api_router.get(
    "/search", 
    response_model=list[Bean]|None,
    response_model_by_alias=True,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
    description="Search beans using either semantic (vector) or keyword (bm25) search, with optional filters. The result is sorted by search score."
)
async def search_beans(
    q: str = Q,
    search_type: Literal["vector", "bm25"] = SEARCH_TYPE,    
    similarity_score: float = SIMILARITY_SCORE,
    kind: Literal["news", "blogs", None] = KIND,
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

@api_router.get(
    "/related", 
    response_model=list[Bean]|None,
    response_model_by_alias=True,
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
    description="Retrieve beans related to the bean identified by the given URL, with optional filters. The result is sorted by newest first."
)
async def get_related(
    url: str = URL,
    kind: Literal["news", "blogs", None] = KIND,
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


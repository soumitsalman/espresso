import logging
from typing import Literal
from datetime import datetime

from fastmcp import FastMCP
from icecream import ic

from app.pybeansack.mongosack import NEWEST
from app.pybeansack.models import *
from app.shared.env import *
from app.shared.utils import *
from app.shared.consts import *

logger: logging.Logger = logging.getLogger(config.app.name)
logger.setLevel(logging.INFO)

### BEANSACK RELATED FILTERING ####
VALUE_EXISTS = { 
    "$exists": True,
    "$ne": None
}

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
    authors: str|list[str],
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
    if authors: filter[K_AUTHOR] = field_value(sources)
    if published_after: filter[K_CREATED] = {"$gte": published_after}
    if with_content: filter.update({
        K_CONTENT: {"$exists": True},
        '$or': [
            {'is_scraped': False},
            {'is_scraped': {"$exists": False}}
        ]
    })
    
    return filter

### URL PATH PARAMETER DEFINITION ###
KIND_PATH = Path(description="Type of beans to retrieve: `news` or `blogs`.")

### QUERY PARAMETER DEFINITIONS ###
Q = Query(
    ..., 
    min_length=3, 
    max_length=512,
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
AUTHORS = Query(
    max_length=MAX_LIMIT, 
    default=None, 
    description="One or more authors to filter beans."
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

### MCP SERVER AND ROUTE DEFINITIONS ###

mcp_router = FastMCP(
    title=config.app.name,
    version="0.0.1", 
    description=config.app.description,
    auth_header="X-API-Key"  # Using X-API-Key for authentication
)

@mcp_router.mcp_get("/sources")
async def get_sources() -> MCPResponse[list[str]]:
    """Get a list of all unique source ids available in the beansack."""
    return MCPResponse(data=sorted(db.beanstore.distinct(K_SOURCE)))

@mcp_router.mcp_get("/categories")
async def get_categories() -> MCPResponse[list[str]]:
    """Get a list of all unique categories (e.g. AI, Cybersecurity, Politics, Software Engineering) available in the beansack."""
    return MCPResponse(data=sorted(db.beanstore.distinct(K_CATEGORIES, {K_CATEGORIES: VALUE_EXISTS})))

@mcp_router.mcp_get("/entities")
async def get_entities() -> MCPResponse[list[str]]:
    """Get a list of all unique named entities available in the beansack."""
    return MCPResponse(data=sorted(db.beanstore.distinct(K_ENTITIES, {K_ENTITIES: VALUE_EXISTS})))

@mcp_router.mcp_get("/regions")
async def get_regions() -> MCPResponse[list[str]]:
    """Get a list of all unique geographic regions available in beansack."""
    return MCPResponse(data=sorted(db.beanstore.distinct(K_REGIONS, {K_REGIONS: VALUE_EXISTS})))

@mcp_router.mcp_get("/authors")
async def get_authors() -> MCPResponse[list[str]]:
    """Get a list of all news article and blog authors whose contents available in beansack."""
    return MCPResponse(data=sorted(db.beanstore.distinct(K_AUTHOR, {K_AUTHOR: VALUE_EXISTS})))

@mcp_router.mcp_get("/new/{kind}")
async def get_beans(
    kind: Literal["news", "blogs"] = KIND_PATH,
    categories: list[str] = CATEGORIES,
    entities: list[str] = ENTITIES,
    regions: list[str] = REGIONS,
    sources: list[str] = SOURCES,
    authors: list[str] = AUTHORS,
    published_after: datetime = PUBLISHED_AFTER,
    with_content: bool = WITH_CONTENT,
    group_by: Literal["cluster_id", "source", "author", None] = GROUP_BY,
    offset: int = OFFSET,
    limit: int = LIMIT
) -> MCPResponse[list[Bean]]:
    """Get a list of new beans (news or blogs) filtered by the provided parameters. The result is sorted by newest first."""
    filter = create_filter(kind, categories, entities, regions, sources, authors, published_after, with_content)
    project = create_projection(with_content) 
    data = db.query_beans(filter=filter, group_by=group_by, sort_by=NEWEST, skip=offset, limit=limit, project=project)
    return MCPResponse(data=data)

@mcp_router.mcp_get("/search/{kind}")
async def search_beans(
    kind: Literal["news", "blogs"] = KIND_PATH,
    q: str = Q,
    search_type: Literal["vector", "bm25"] = SEARCH_TYPE,    
    similarity_score: float = SIMILARITY_SCORE,
    categories: list[str] = CATEGORIES,
    entities: list[str] = ENTITIES,
    regions: list[str] = REGIONS,
    sources: list[str] = SOURCES,
    authors: list[str] = AUTHORS,
    published_after: datetime = PUBLISHED_AFTER,
    with_content: bool = WITH_CONTENT,
    group_by: Literal["cluster_id", "source", "author", None] = GROUP_BY,
    offset: int = OFFSET,
    limit: int = LIMIT
) -> MCPResponse[list[Bean]]:
    """Search beans using either semantic (vector) or keyword (bm25) search, with optional filters. The result is sorted by search score."""
    filter = create_filter(kind, categories, entities, regions, sources, authors, published_after, with_content)
    project = create_projection(with_content) 
    if search_type == "vector":
        data = db.vector_search_beans(
            embedding=embedder.embed_query(q), 
            similarity_score=similarity_score, 
            filter=filter, 
            group_by=group_by, 
            skip=offset, 
            limit=limit, 
            project=project
        )
    else:
        data = db.text_search_beans(
            query=q, 
            filter=filter, 
            group_by=group_by, 
            skip=offset, 
            limit=limit, 
            project=project
        )
    return MCPResponse(data=data)

@mcp_router.mcp_get("/related")
async def get_related(
    url: str = URL,
    kind: Literal["news", "blogs", None] = KIND,
    categories: list[str] = CATEGORIES,
    entities: list[str] = ENTITIES,
    regions: list[str] = REGIONS,
    sources: list[str] = SOURCES,
    authors: list[str] = AUTHORS,
    published_after: datetime = PUBLISHED_AFTER,
    with_content: bool = WITH_CONTENT,
    limit: int = LIMIT
) -> MCPResponse[list[Bean]]:
    """Retrieve beans related to the bean identified by the given URL, with optional filters. The result is sorted by newest first."""
    filter = create_filter(kind, categories, entities, regions, sources, authors, published_after, with_content)
    project = create_projection(with_content) 
    data = db.query_related_beans(url, filter=filter, sort_by=NEWEST, limit=limit, project=project)
    return MCPResponse(data=data)

def run():
    mcp_router.run(host="0.0.0.0", port=8081)  # Using a different port from FastAPI server
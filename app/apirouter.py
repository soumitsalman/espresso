from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from typing import Literal
from dotenv import load_dotenv

from pybeansack.models import *
from app.shared import AppContext
from app.shared.consts import *

### App Info ###
NAME = "Espresso API"
DESCRIPTION = "API for Espresso (Alpha)"
VERSION = "0.0.1"
FAVICON = "https://cafecito-assets.sfo3.cdn.digitaloceanspaces.com/espresso-favicon.ico"

### DB QUERY CONSTANTS ###
DEFAULT_ACCURACY = 0.75
DEFAULT_LIMIT = 16

CORE_BEAN_FIELDS = [
    K_URL, K_KIND,
    K_TITLE, K_SUMMARY,
    K_AUTHOR, K_SOURCE, K_IMAGEURL, K_CREATED, 
    K_CATEGORIES, K_SENTIMENTS, K_REGIONS, K_ENTITIES
]
CORE_PUBLISHER_FIELDS = [K_SOURCE, K_BASE_URL, K_SITE_NAME, K_DESCRIPTION, K_FAVICON]

### QUERY PARAMETER DEFINITIONS ###
Q = Query(
    default=None, 
    min_length=3, 
    max_length=512,
    description="The search query string. Minimum length is 3 characters."
)
SEARCH_TYPE = Query(
    default="vector", 
    description="Indicate if the search should be a semantic (vector) search or a text keyword (bm25) search."
)
ACCURACY = Query(
    default=DEFAULT_ACCURACY, 
    ge=0, le=1,
    description="Minimum cosine similarity score (only applicable to vector search)."
)
URL = Query(
    ..., 
    min_length=10, 
    description="The URL of the bean for which related beans are to be found. Minimum length is 10 characters."
)
KIND = Query(
    default=None, 
    description="Type of bean to query: 'news', 'blog', or keep it unspecified for both."
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
PUBLISHED_SINCE = Query(
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
    default=DEFAULT_LIMIT, 
    description="Maximum number of items to return."
)

db_context: AppContext = None

### ROUTER AND ROUTE DEFINITIONS ###
@asynccontextmanager
async def lifespan(app: FastAPI):    
    load_dotenv()
    global db_context
    db_context = AppContext(
        db_kwargs={
            "db_type": os.getenv("DB_TYPE"), 
            "pg_connection_string": os.getenv("PG_CONNECTION_STRING")
        },
        embedder_kwargs={
            "model_name": os.getenv('EMBEDDER_MODEL'), 
            "ctx_len": int(os.getenv('EMBEDDER_CTX', 512))
        }
    )    
    yield    

    db_context.close()

app = FastAPI(title=NAME, version=VERSION, description=DESCRIPTION, lifespan=lifespan)
# app.mount("/docs", StaticFiles(directory="app/assets/docs"), "docs")

@app.get("/favicon.ico")
async def get_favicon():
    return RedirectResponse(FAVICON)

@app.get(
    "/categories", 
    response_model=list[str]|None,
    description="Get a list of all unique categories (e.g. AI, Cybersecurity, Politics, Software Engineering) available in the beansack."
)
async def get_categories(offset: int = OFFSET, limit: int = LIMIT) -> list[str]:
    return db_context.db.distinct_categories(limit=limit, offset=offset)

@app.get(
    "/entities", 
    response_model=list[str]|None,
    description="Get a list of all unique named entities (people, organizations, products) available in the beansack."
)
async def get_entities(offset: int = OFFSET, limit: int = LIMIT) -> list[str]:
    return db_context.db.distinct_entities(limit=limit, offset=offset)

@app.get(
    "/regions", 
    response_model=list[str]|None,
    description="Get a list of all unique geographic regions available in beansack."
)
async def get_regions(offset: int = OFFSET, limit: int = LIMIT) -> list[str]:
    return db_context.db.distinct_regions(limit=limit, offset=offset)
@app.get(
    "/articles/latest", 
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
    description="Get a list of new beans (news or blogs) filtered by the provided parameters. The result is sorted by newest first."
)
async def get_beans(
    q: str = Q,
    acc: float = ACCURACY,
    kind: Literal[NEWS, BLOG] = KIND,
    categories: list[str] = CATEGORIES,
    entities: list[str] = ENTITIES,
    regions: list[str] = REGIONS,
    sources: list[str] = SOURCES,
    published_since: datetime = PUBLISHED_SINCE,
    # TODO: with_content: bool = WITH_CONTENT,
    offset: int = OFFSET,
    limit: int = LIMIT
) -> Optional[list[Bean]]:    
    return db_context.db.query_latest_beans(
        kind=kind,
        created=published_since,
        categories=categories,
        regions=regions,
        entities=entities,
        sources=sources,
        embedding=db_context.embed_query(q) if q else None,
        distance=1-acc if q else 0,
        limit=limit,
        offset=offset,
        # TODO: when with_content is True add condition and extend project
        columns=CORE_BEAN_FIELDS
    )

# TODO: add routes for /trending and /related

# @api.get(
#     "/related", 
#     response_model=list[Bean]|None,
#     response_model_by_alias=True,
#     response_model_exclude_none=True,
#     response_model_exclude_unset=True,
#     description="Retrieve beans related to the bean identified by the given URL, with optional filters. The result is sorted by newest first."
# )
# async def get_related(
#     url: str = URL,
#     kind: Literal["news", "blogs", None] = KIND,
#     categories: list[str] = CATEGORIES,
#     entities: list[str] = ENTITIES,
#     regions: list[str] = REGIONS,
#     sources: list[str] = SOURCES,
#     authors: list[str] = AUTHORS,
#     published_after: datetime = PUBLISHED_AFTER,
#     with_content: bool = WITH_CONTENT,
#     limit: int = LIMIT
# ) -> list[Bean]:
#     """
#     Retrieves the related beans to the given bean.
#     """  
#     filter = create_filter(kind, categories, entities, regions, sources, authors, published_after, with_content)
#     project = create_projection(with_content) 
#     return db.query_related_beans(url, filter=filter, sort_by=NEWEST, limit=limit, project = project)

@app.get(
    "/publishers", 
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
    description="Get a list of all unique source ids available in the beansack."
)
async def get_publishers(
    sources: list[str] = Query(..., max_length=MAX_LIMIT, description="One or more source ids to filter publishers."), 
    offset: int = OFFSET, 
    limit: int = LIMIT
) -> Optional[list[Publisher]]:
    return db_context.db.query_publishers(sources=sources, limit=limit, offset=offset, columns=CORE_PUBLISHER_FIELDS)

# BUG: the offset and limit is not working as expected
@app.get(
    "/publishers/sources", 
    description="Get a list of unique source ids available in the beansack."
)
async def get_publishers(offset: int = OFFSET, limit: int = LIMIT) -> Optional[list[str]]:
    return db_context.db.distinct_publishers(limit=limit, offset=offset)



from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Query, HTTPException, Header, Depends, Request
from fastapi.responses import RedirectResponse, FileResponse
from typing import Literal
from dotenv import load_dotenv
import os

from pybeansack.models import *
from app.shared import AppContext
from app.shared.consts import *

load_dotenv()

### App Info ###
NAME = "Espresso News"
DESCRIPTION = "Espresso News API is an intelligent news aggregation and search service that curates fresh content from RSS feeds using AI-powered natural language queries and filters. Access trending articles, publishers, categories, and entities with fast JSON responses, perfect for developers building news apps or integrating smart content discovery."
VERSION = "0.0.2"
FAVICON = "app/assets/images/espresso-api.png"

### DB QUERY CONSTANTS ###
DEFAULT_ACCURACY = 0.75
DEFAULT_LIMIT = 16

UNRESTRICTED_CONTENT = ["restricted_content IS NULL", "content IS NOT NULL"]
CORE_BEAN_FIELDS = [
    K_URL, K_KIND,
    K_TITLE, K_SUMMARY,
    K_AUTHOR, K_SOURCE, K_IMAGEURL, K_CREATED, 
    K_CATEGORIES, K_SENTIMENTS, K_REGIONS, K_ENTITIES
]
EXTENDED_BEAN_FIELDS = CORE_BEAN_FIELDS + [K_CONTENT]
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
    description="The URL of the article for which related articles are to be found. Minimum length is 10 characters."
)
KIND = Query(
    default=None, 
    description="Type of article to query: 'news', 'blog', or keep it unspecified for both."
)
CATEGORIES = Query(
    max_length=MAX_LIMIT, 
    default=None, 
    description="One or more categories (case sensitive) to filter articles."
)
ENTITIES = Query(
    max_length=MAX_LIMIT, 
    default=None, 
    description="One or more named entities (case sensitive) to filter articles."
)
REGIONS = Query(
    max_length=MAX_LIMIT, 
    default=None, 
    description="One or more regions (case sensitive) to filter articles."
)
SOURCES = Query(
    max_length=MAX_LIMIT, 
    default=None, 
    description="One or more publisher ids (case sensitive) to filter articles."
)
AUTHORS = Query(
    max_length=MAX_LIMIT, 
    default=None, 
    description="One or more authors (case sensitive) to filter articles."
)
PUBLISHED_SINCE = Query(
    default=None, 
    description="Only return articles published on or after this datetime."
)
WITH_CONTENT = Query(
    default=False, 
    description="Include full text content of the articles. This applies ONLY to articles for which the full content is available."
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
    global db_context
    
    # Load API keys configuration
    api_keys = os.getenv("API_KEYS", "").split(";")
    api_keys = [kv.strip().split("=", maxsplit=1) for kv in api_keys if kv.strip()]
    api_keys = {kv[0].strip(): kv[1].strip() for kv in api_keys}
    
    db_context = AppContext(
        db_kwargs={
            "db_type": os.getenv("DB_TYPE"), 
            "pg_connection_string": os.getenv("PG_CONNECTION_STRING")
        },
        embedder_kwargs={
            "model_name": os.getenv('EMBEDDER_MODEL'), 
            "ctx_len": int(os.getenv('EMBEDDER_CTX', 512))
        },
        api_keys=api_keys
    )    
    yield    

    db_context.close()

def verify_api_key(request: Request):
    # Check each allowed header in the request
    for header, value in db_context.settings['api_keys'].items():
        provided_value = request.headers.get(header)
        
        if not provided_value: continue
        # Remove Bearer prefix if present
        provided_value = provided_value.removeprefix("Bearer ").strip()
        if provided_value == value: return provided_value
    
    raise HTTPException(status_code=401, detail="Invalid API Key")

api_key_dependency = Depends(verify_api_key)

app = FastAPI(title=NAME, version=VERSION, description=DESCRIPTION, lifespan=lifespan)

# @app.get("/")
# async def root():
#     return FileResponse("app/assets/index.html")

@app.get("/health", description="Performs a health check on the API service.")
async def health_check():
    return {"status": "alive"}

@app.get("/favicon.ico", description="Retrieves the favicon for the API.")
async def get_favicon():
    return FileResponse(FAVICON, media_type="image/png")

@app.get(
    "/categories", 
    dependencies=[api_key_dependency],
    description="Retrieves a list of unique content categories from the articles, such as AI, Cybersecurity, Politics, and Software Engineering."
)
async def get_categories(offset: int = OFFSET, limit: int = LIMIT) -> list[str]:
    return db_context.db.distinct_categories(limit=limit, offset=offset)

@app.get(
    "/entities", 
    dependencies=[api_key_dependency],
    description="Retrieves a list of unique named entities (people, organizations, products) mentioned in the articles."
)
async def get_entities(offset: int = OFFSET, limit: int = LIMIT) -> list[str]:
    return db_context.db.distinct_entities(limit=limit, offset=offset)

@app.get(
    "/regions", 
    dependencies=[api_key_dependency],
    description="Retrieves a list of unique geographic regions mentioned in the articles."
)
async def get_regions(offset: int = OFFSET, limit: int = LIMIT) -> list[str]:
    return db_context.db.distinct_regions(limit=limit, offset=offset)

@app.get(
    "/articles/latest", 
    dependencies=[Depends(verify_api_key)],
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
    response_model_exclude=[K_COLLECTED, K_RESTRICTED_CONTENT, "title_length", "summary_length", "content_length", K_EMBEDDING, K_GIST],
    description="Searches for the latest articles (news or blog posts) sorted by publication date in descending order (newest first)."
)
async def get_latest_articles(
    q: str = Q,
    acc: float = ACCURACY,
    kind: Literal[NEWS, BLOG] = KIND,
    categories: list[str] = CATEGORIES,
    entities: list[str] = ENTITIES,
    regions: list[str] = REGIONS,
    sources: list[str] = SOURCES,
    published_since: datetime = PUBLISHED_SINCE,
    with_content: bool = WITH_CONTENT,
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
        conditions=UNRESTRICTED_CONTENT if with_content else None,
        limit=limit,
        offset=offset,        
        columns=EXTENDED_BEAN_FIELDS if with_content else CORE_BEAN_FIELDS
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
    dependencies=[api_key_dependency],
    response_model_exclude_none=True,
    response_model_exclude_unset=True,
    response_model_exclude=[K_RSS_FEED, K_COLLECTED],
    description="Retrieves publisher metadata filtered by one or more publisher IDs."
)
async def get_publishers(
    sources: list[str] = Query(..., max_length=MAX_LIMIT, description="One or more source ids to filter publishers."), 
    offset: int = OFFSET, 
    limit: int = LIMIT
) -> Optional[list[Publisher]]:
    return db_context.db.query_publishers(sources=sources, limit=limit, offset=offset, columns=CORE_PUBLISHER_FIELDS)

@app.get(
    "/publishers/sources", 
    dependencies=[api_key_dependency],
    description="Retrieves a list of unique publisher IDs from which the articles are sourced."
)
async def get_publishers(offset: int = OFFSET, limit: int = LIMIT) -> Optional[list[str]]:
    return db_context.db.distinct_publishers(limit=limit, offset=offset)



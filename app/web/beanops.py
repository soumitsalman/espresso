import re
import threading
from memoization import cached
from icecream import ic
from sentence_transformers import SentenceTransformer
from pybeansack.mongosack import LATEST
from pybeansack.models import *
from app.shared.utils import *
from app.shared.env import *
from app.shared.consts import *
from app.web.context import *

CACHE_SIZE = 100
BEAN_HEADER_FIELDS = {K_URL: 1, K_TITLE: 1, K_KIND: 1, K_IMAGEURL: 1, K_SOURCE: 1, K_SITE_NAME: 1, K_CATEGORIES: 1, K_REGIONS: 1, K_CREATED: 1, K_LIKES: 1, K_COMMENTS: 1, K_RELATED: 1, K_SHARES: 1}
BEAN_BODY_FIELDS = {K_URL: 1, K_ENTITIES: 1, K_AUTHOR: 1}
if config.filters.bean.body == "whole": BEAN_BODY_FIELDS.update({K_SUMMARY: 1})

# Initialize the model and tokenizer globally
embedder: SentenceTransformer = None
embedder_lock = threading.Lock()

@cached(max_size=CACHE_SIZE, ttl=HALF_HOUR)
def embed_query(query: str) -> list[float]:
    """Generate embeddings using the ONNX model."""
    global embedder
    with embedder_lock:
        if not embedder:
            embedder = SentenceTransformer(config.embedder.path, cache_folder=".models", tokenizer_kwargs={"truncation": True})
        vec = embedder.encode("query: "+query, convert_to_numpy=False).tolist()
    return vec

@cached(max_size=1, ttl=ONE_WEEK)
def get_all_sources():
    return sorted(db.beanstore.distinct(K_SOURCE))

def load_bean_body(bean: Bean):
    res = db.beanstore.find_one(filter={K_ID: bean.url}, projection=BEAN_BODY_FIELDS)
    bean.tags = res.get(K_TAGS)
    bean.summary = res.get(K_SUMMARY)
    return bean

@cached(max_size=CACHE_SIZE, ttl=ONE_HOUR)
def get_beans_for_home(kind: str, tags: str|list[str], sources: str|list[str], last_ndays: int, sort_by, start: int, limit: int):
    """get one bean per cluster and per source"""
    filter = create_filter(kind, tags, sources, None, last_ndays, None)
    return db.query_beans(filter, K_SOURCE, sort_by, start, limit, BEAN_HEADER_FIELDS)

@cached(max_size=CACHE_SIZE, ttl=HALF_HOUR)
def get_beans_for_page(page: Page, kind: str, tags: str|list[str], sort_by, start: int, limit: int):
    filter=create_filter(
        kinds = kind, 
        tags = [tags, page.query_tags], 
        sources = page.query_sources, 
        urls = page.query_urls,
        created_in_last_ndays = None, 
        updated_in_last_ndays = None
    )
    # if the barista is primarily based on specific urls, then just search for those
    if page.query_urls: return db.query_beans(filter=filter, sort_by=sort_by, skip=start, limit=limit, project=BEAN_HEADER_FIELDS)
    if page.query_embedding: return db.vector_search_beans(embedding=page.query_embedding, similarity_score=page.query_distance or config.filters.bean.default_accuracy, filter=filter, group_by=K_CLUSTER_ID, sort_by=sort_by, skip=start, limit=limit, project=BEAN_HEADER_FIELDS)
    if page.query_tags or page.query_sources: return db.query_beans(filter=filter, group_by=K_CLUSTER_ID, sort_by=sort_by, skip=start, limit=limit, project=BEAN_HEADER_FIELDS)   

@cached(max_size=CACHE_SIZE, ttl=FOUR_HOURS)
def get_filter_tags_for_page(page: Page, start: int, limit: int):
    filter=create_filter(
        kind = None,
        tags = page.query_tags,
        sources = page.query_sources, 
        urls = page.query_urls,
        created_in_last_ndays = None, 
        updated_in_last_ndays = None        
    )
    if page.query_embedding: return db.vector_search_tags(page.query_embedding, page.query_distance or config.filters.bean.default_accuracy, filter, tag_field = K_ENTITIES, remove_tags=page.query_tags, skip=start, limit=limit)
    if page.query_urls or page.query_tags or page.query_sources: return db.query_tags(filter, tag_field = K_ENTITIES, remove_tags=page.query_tags, skip=start, limit=limit)

@cached(max_size=CACHE_SIZE, ttl=HALF_HOUR)
def get_beans_for_source(source_id: str, kind: str, tags: str|list[str]|list[list[str]], last_ndays: int, sort_by, start: int, limit: int):
    """Retrieves news articles, social media posts, blog articles from the feed source"""  
    filter=create_filter(kind, tags, source_id, None, last_ndays, None)
    return db.query_beans(filter=filter, group_by=K_CLUSTER_ID, sort_by=sort_by, skip=start, limit=limit, project=BEAN_HEADER_FIELDS)   

@cached(max_size=CACHE_SIZE, ttl=HALF_HOUR)
def search_beans(query: str, accuracy: float, kind: str, tags: str|list[str]|list[list[str]], sources: str|list[str], last_ndays: int, start: int, limit: int):
    """Searches and looks for news articles, social media posts, blog articles that match user interest, topic or query represented by `topic`."""  
    filter=create_filter(kind, tags, sources, None, last_ndays, None)
    accuracy = accuracy or config.filters.bean.default_accuracy
    if is_valid_url(query): return db.vector_search_similar_beans(query, accuracy, filter, None, start, limit, BEAN_HEADER_FIELDS)
    if query: return db.vector_search_beans(embedding=embed_query(query), similarity_score=accuracy, filter=filter, skip=start, limit=limit, project=BEAN_HEADER_FIELDS)    
    if tags or sources: return db.query_beans(filter=filter, group_by=K_CLUSTER_ID, sort_by=LATEST, skip=start, limit=limit, project=BEAN_HEADER_FIELDS)


@cached(max_size=CACHE_SIZE, ttl=ONE_HOUR)
def search_filter_tags(query: str, accuracy: float, tags: str|list[str]|list[list[str]], sources: str|list[str], last_ndays: int, start: int, limit: int) -> list[Bean]:
    filter=create_filter(None, tags, sources, None, last_ndays, None)
    accuracy = accuracy or config.filters.bean.default_accuracy
    # if is_valid_url(query): db.vector_search_tags(
    #     bean_embedding=embed_query(query), 
    #     bean_similarity_score=accuracy or config.filters.bean.default_accuracy, 
    #     bean_filter=filter, 
    #     remove_tags=tags,
    #     skip=start, limit=limit) 

    if query: return db.vector_search_tags(
        bean_embedding=embed_query(query), 
        bean_similarity_score=accuracy,         
        bean_filter=filter, 
        tag_field = K_ENTITIES,
        remove_tags=tags,
        skip=start, limit=limit
    )  
    return db.query_tags(bean_filter=filter, tag_field=K_ENTITIES, remove_tags=tags, skip=start, limit=limit)
    
@cached(max_size=CACHE_SIZE, ttl=ONE_HOUR)
def count_search_beans(query: str, accuracy: float, kind: str, tags: str|list[str]|list[list[str]], sources: str|list[str], last_ndays: int, limit: int) -> int:
    filter=create_filter(kind, tags, sources, None, last_ndays, None)
    accuracy = accuracy or config.filters.bean.default_accuracy
    if is_valid_url(query): return db.count_vector_search_similar_beans(query, accuracy, filter=filter, group_by=None, limit=limit)
    if query: return db.count_vector_search_beans(embedding=embed_query(query), similarity_score=accuracy, filter=filter, limit=limit)  
    if tags or sources: return db.count_beans(filter=filter, group_by=K_CLUSTER_ID, limit=limit)
    return 0
    
@cached(max_size=CACHE_SIZE, ttl=FOUR_HOURS)
def get_related_beans(url: str, kind: str, tags: str|list[str]|list[list[str]], sources: str|list[str], last_ndays: int):
    filter = create_filter(kind, tags, sources, None, last_ndays, None)
    return db.query_related_beans(url=url, filter=filter, limit=config.filters.bean.max_related, project=BEAN_HEADER_FIELDS) 

PAGE_MINIMAL_FIELDS = {K_ID: 1, K_TITLE: 1}
PAGE_DEFAULT_FIELDS = {K_ID: 1, K_TITLE: 1, K_DESCRIPTION: 1, "public": 1, "owner": 1}
PAGE_EMBEDDING_FIELDS = {K_ID: 1, K_EMBEDDING: 1}

@cached(max_size=CACHE_SIZE, ttl=ONE_HOUR)
def get_page(id: str) -> Page|None:
    return db.get_page(id, PAGE_DEFAULT_FIELDS)

@cached(max_size=CACHE_SIZE, ttl=FOUR_HOURS)
def get_pages(ids: list[str]) -> list[Page]:
    return db.get_pages(ids, PAGE_DEFAULT_FIELDS)

@cached(max_size=CACHE_SIZE, ttl=FOUR_HOURS)
def get_page_suggestions(context: Context):
    return db.sample_pages(5, PAGE_DEFAULT_FIELDS)

@cached(max_size=CACHE_SIZE, ttl=HALF_HOUR)
def search_pages(query: str):
    return db.search_pages(query, PAGE_DEFAULT_FIELDS)

def is_bookmarked(context: Context, url: str):
    if not context.is_registered: return False
    return db.is_bookmarked(context.user, url)

def create_filter(
    kind: str,
    tags: str|list[str]|list[list[str]],
    sources: str|list[str],
    urls: str|list[str],
    created_in_last_ndays: int,
    updated_in_last_ndays: int
) -> dict:   
    filter = {
        K_CATEGORIES: {"$exists": True},
        K_ENTITIES: {"$exists": True},
        K_REGIONS: {"$exists": True}
    }
    if kind: filter[K_KIND] = kind
    if tags: filter["$and"] = tags
    if sources: filter["$or"] = [
        {K_SOURCE: case_insensitive(sources)},
        {K_SHARED_IN: case_insensitive(sources)}
    ]
    if urls: filter[K_URL] = field_value(urls)
    if created_in_last_ndays: filter[K_CREATED] = {"$gte": ndays_ago(created_in_last_ndays)}
    if updated_in_last_ndays: filter[K_UPDATED] = {"$gte": ndays_ago(updated_in_last_ndays)}  

    if isinstance(tags, str): filter[K_TAGS] = lower_case(tags)
    elif isinstance(tags, list):
        if all(isinstance(tag, str) for tag in tags): filter[K_TAGS] = lower_case(tags)
        elif any(isinstance(tag, list) for tag in tags): filter["$and"] = [{K_TAGS: lower_case(tag)} for tag in tags] 
    
    return filter

# def _create_filter(
#         tags: str|list[str]|list[list[str]], 
#         kinds: str|list[str], 
#         sources: str|list[str],
#         urls: str|list[str],
#         created_in_last_ndays: int,
#         updated_in_last_ndays: int) -> dict:   
#     filter = {}
#     if kinds: filter[K_KIND] = lower_case(kinds)

#     if tags: # non-empty or non-null value of tags is important
        
#         if isinstance(tags, str):
#             filter[K_TAGS] = tags            
#         if isinstance(tags, list):
#             if all(isinstance(tag, str) for tag in tags): 
#                 filter[K_TAGS] = {"$in": tags}
#             else: 
#                 tag_filters = [{K_TAGS: field_value(taglist)} for taglist in tags if taglist]
#                 if tag_filters: filter["$and"] = tag_filters
#     if sources:
#         # TODO: make it look into both source field of the beans and the channel field of the chatters
#         filter["$or"] = [
#             {K_SOURCE: case_insensitive(sources)},
#             {"shared_in": case_insensitive(sources)}
#         ]
#     if urls:
#         filter[K_URL] = field_value(urls)
#     if created_in_last_ndays:
#         filter[K_CREATED] = {"$gte": ndays_ago(created_in_last_ndays)}
#     if updated_in_last_ndays: 
#         filter[K_UPDATED] = {"$gte": ndays_ago(updated_in_last_ndays)}  
#     return filter


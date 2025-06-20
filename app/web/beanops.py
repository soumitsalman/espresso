from memoization import cached
from icecream import ic
from nicegui import run
from app.pybeansack.mongosack import *
from app.pybeansack.models import *
from app.shared.utils import *
from app.shared.env import *
from app.shared.consts import *
from app.web.context import *

CACHE_SIZE = 100

BEAN_HEADER_FIELDS = {
    K_URL: 1, K_TITLE: 1,
    K_KIND: 1, K_IMAGEURL: 1, 
    K_SOURCE: 1, K_SITE_NAME: 1, K_SITE_BASE_URL: 1, K_AUTHOR: 1,
    K_CATEGORIES: 1, 
    K_REGIONS: 1, 
    K_CREATED: 1, 
    K_LIKES: 1, K_COMMENTS: 1, K_RELATED: 1, K_SHARES: 1
}
BEAN_SUMMARY_FIELDS = {K_URL: 1, K_ENTITIES: 1, K_SUMMARY: 1}
WHOLE_BEAN_FIELDS = {
    K_CONTENT: 0, K_IS_SCRAPED: 0,
    K_COLLECTED: 0, 
    K_SEARCH_SCORE: 0, K_CLUSTER_ID: 0,
    K_TAGS: 0, K_GIST: 0, 
    K_TRENDSCORE: 0, 
    K_NUM_WORDS_CONTENT: 0, K_NUM_WORDS_SUMMARY:0, K_NUM_WORDS_TITLE:0
}

@cached(max_size=1, ttl=ONE_WEEK)
def get_all_sources():
    return sorted(db.beanstore.distinct(K_SOURCE))

def load_bean_body(bean: Bean):
    res = db.get_bean(url=bean.url, project=BEAN_SUMMARY_FIELDS)
    bean.entities = res.entities
    bean.author = res.author
    bean.summary = res.summary
    return bean

def get_generated_bean(url: str):
    bean = db.beanstore.find_one(filter={K_ID: url, K_KIND: GENERATED}, projection={K_EMBEDDING: 0, K_CONTENT: 0})
    if bean: return GeneratedBean(**bean)

@cached(max_size=CACHE_SIZE, ttl=ONE_HOUR)
def get_beans_for_home(kind: str, tags: str|list[str], sources: str|list[str], last_ndays: int, sort_by, start: int, limit: int):
    """get one bean per cluster and per source"""
    filter = create_filter(kind, tags, sources, None, last_ndays, None)
    return db.query_beans(filter, [K_SOURCE, K_CLUSTER_ID], sort_by, start, limit, BEAN_HEADER_FIELDS)

@cached(max_size=CACHE_SIZE, ttl=HALF_HOUR)
def get_beans_for_stored_page(page: Page, kind: str, tags: str|list[str], last_ndays: int, sort_by, start: int, limit: int):
    filter=create_filter(
        kind = kind, 
        tags = [tags, page.query_tags], 
        sources = page.query_sources, 
        urls = page.query_urls,
        created_in_last_ndays = last_ndays, 
        updated_in_last_ndays = None
    )
    # if the barista is primarily based on specific urls, then just search for those
    if page.query_urls: return db.query_beans(filter=filter, sort_by=sort_by, skip=start, limit=limit, project=BEAN_HEADER_FIELDS)
    if page.query_embedding: return db.vector_search_beans(embedding=page.query_embedding, similarity_score=page.query_distance or config.filters.page.default_accuracy, filter=filter, group_by=K_CLUSTER_ID, sort_by=sort_by, skip=start, limit=limit, project=BEAN_HEADER_FIELDS)
    if page.query_tags or page.query_sources: return db.query_beans(filter=filter, group_by=K_CLUSTER_ID, sort_by=sort_by, skip=start, limit=limit, project=BEAN_HEADER_FIELDS)   

# @cached(max_size=CACHE_SIZE, ttl=FOUR_HOURS)
def get_generated_beans(page: Page, tags, last_ndays: int, start: int, limit: int):
    filter=create_filter_for_generated_bean(page, tags, last_ndays)
    if page and page.query_embedding: return db.vector_search_beans(
        embedding=page.query_embedding, 
        similarity_score=(1 - page.query_distance) if page.query_distance else config.filters.page.default_accuracy, 
        filter=filter, sort_by=NEWEST, 
        skip=start, limit=limit, project=BEAN_HEADER_FIELDS
    )
    return db.query_beans(filter=filter, sort_by=NEWEST, skip=start, limit=limit, project=BEAN_HEADER_FIELDS)   

# @cached(max_size=CACHE_SIZE, ttl=HALF_HOUR)
def get_beans_for_custom_page(kind: str, tags: str|list[str]|list[list[str]], sources: str|list[str], last_ndays: int, sort_by, start: int, limit: int):
    """Searches and looks for news articles, social media posts, blog articles that match user interest, topic or query represented by `topic`."""  
    filter=create_filter(kind, tags, sources, None, last_ndays, None)
    return db.query_beans(filter=filter, group_by=K_CLUSTER_ID, sort_by=sort_by, skip=start, limit=limit, project=BEAN_HEADER_FIELDS)

# @cached(max_size=CACHE_SIZE, ttl=HALF_HOUR)
def search_beans(query: str, accuracy: float, kind: str, tags: str|list[str]|list[list[str]], sources: str|list[str], last_ndays: int, start: int, limit: int):
    """Searches and looks for news articles, social media posts, blog articles that match user interest, topic or query represented by `topic`."""  
    filter=create_filter(kind, tags, sources, None, last_ndays, None)
    accuracy = accuracy or config.filters.page.default_accuracy
    if query: return db.vector_search_beans(embedding=_embed(query), similarity_score=accuracy, filter=filter, skip=start, limit=limit, project=BEAN_HEADER_FIELDS)    

# @cached(max_size=CACHE_SIZE, ttl=FOUR_HOURS)
def get_similar_beans(bean: Bean, kind: str|list[str], tags: str|list[str]|list[list[str]], sources: str|list[str], last_ndays: int, sort_by, start: int, limit: int):
    filter=create_filter(kind, tags, sources, None, last_ndays, None)
    accuracy = config.filters.page.default_accuracy
    if bean.embedding: return db.vector_search_beans(bean.embedding, accuracy, filter, None, sort_by, start, limit, BEAN_HEADER_FIELDS)
    else: return db.vector_search_similar_beans(bean.url, accuracy, filter, None, start, limit, BEAN_HEADER_FIELDS)

def get_beans_in_cluster(url: str, kind: str|list[str], tags: str|list[str]|list[list[str]], sources: str|list[str], last_ndays: int, start: int, limit: int):
    filter = create_filter(kind, tags, sources, None, last_ndays, None)
    return db.query_beans_in_cluster(url=url, filter=filter, sort_by=None, skip=start, limit=limit, project={**BEAN_HEADER_FIELDS, **BEAN_SUMMARY_FIELDS}) 

@cached(max_size=CACHE_SIZE, ttl=FOUR_HOURS)
def count_generated_beans(page: Page, tags, last_ndays: int, limit: int):
    filter=create_filter_for_generated_bean(page, tags, last_ndays)
    if page and page.query_embedding: return db.count_vector_search_beans(
        embedding=page.query_embedding, 
        similarity_score=(1 - page.query_distance) if page.query_distance else config.filters.page.default_accuracy, 
        filter=filter, limit=limit
    )
    return db.count_beans(filter=filter, limit=limit)  

# @cached(max_size=CACHE_SIZE, ttl=ONE_HOUR)
def count_search_beans(query: str, accuracy: float, kind: str, tags: str|list[str]|list[list[str]], sources: str|list[str], last_ndays: int, limit: int) -> int:
    filter=create_filter(kind, tags, sources, None, last_ndays, None)
    accuracy = accuracy or config.filters.page.default_accuracy
    if query: return db.count_vector_search_beans(embedding=_embed(query), similarity_score=accuracy, filter=filter, limit=limit)  
    return 0

@cached(max_size=CACHE_SIZE, ttl=FOUR_HOURS)
def count_similar_beans(bean: Bean, kind: str|list[str], tags: str|list[str]|list[list[str]], sources: str|list[str], last_ndays: int, limit: int):
    filter=create_filter(kind, tags, sources, None, last_ndays, None)
    accuracy = config.filters.page.default_accuracy
    if bean.embedding: return db.count_vector_search_beans(bean.embedding, accuracy, filter, None, limit)
    else: return db.count_vector_search_similar_beans(bean.url, accuracy, filter=filter, group_by=None, limit=limit)

@cached(max_size=CACHE_SIZE, ttl=FOUR_HOURS)
def get_filter_tags_for_stored_page(page: Page, last_ndays: int, start: int, limit: int):
    filter=create_filter(
        kind = None,
        tags = page.query_tags,
        sources = page.query_sources, 
        urls = page.query_urls,
        created_in_last_ndays = last_ndays, 
        updated_in_last_ndays = None        
    )
    if page.query_embedding: return db.vector_search_tags(page.query_embedding, page.query_distance or config.filters.page.default_accuracy, filter, tag_field = K_ENTITIES, remove_tags=page.query_tags, skip=start, limit=limit)
    if page.query_urls or page.query_tags or page.query_sources: return db.query_tags(filter, tag_field = K_ENTITIES, remove_tags=page.query_tags, skip=start, limit=limit)

@cached(max_size=CACHE_SIZE, ttl=HALF_HOUR)
def get_filter_tags_for_custom_page(tags: str|list[str]|list[list[str]], sources: str|list[str], last_ndays: int, start: int, limit: int):
    """Searches and looks for news articles, social media posts, blog articles that match user interest, topic or query represented by `topic`."""  
    filter=create_filter(None, tags, sources, None, last_ndays, None)
    return db.query_tags(bean_filter=filter, tag_field=K_ENTITIES, remove_tags=tags, skip=start, limit=limit)

# @cached(max_size=CACHE_SIZE, ttl=ONE_HOUR)
def search_filter_tags(query: str, accuracy: float, tags: str|list[str]|list[list[str]], sources: str|list[str], last_ndays: int, start: int, limit: int) -> list[Bean]:
    filter=create_filter(None, tags, sources, None, last_ndays, None)
    accuracy = accuracy or config.filters.page.default_accuracy
    if query: return db.vector_search_tags(
        bean_embedding=_embed(query), 
        bean_similarity_score=accuracy,         
        bean_filter=filter, 
        tag_field = K_ENTITIES,
        remove_tags=tags,
        skip=start, limit=limit
    )  
 
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
    pages = None
    if context.is_stored_page: pages = db.get_related_pages(context.page.id, PAGE_MINIMAL_FIELDS)
    # TODO: extend it by making a search using text
    if not pages: pages = db.sample_pages(5, PAGE_MINIMAL_FIELDS)
    return pages

@cached(max_size=CACHE_SIZE, ttl=HALF_HOUR)
def search_pages(query: str):
    return db.search_pages(query, PAGE_DEFAULT_FIELDS)

def is_bookmarked(context: Context, url: str):
    if not context.is_user_registered: return False
    return db.is_bookmarked(context.user, url)

def create_filter(
    kind: str|list[str],
    tags: str|list[str]|list[list[str]],
    sources: str|list[str],
    urls: str|list[str],
    created_in_last_ndays: int,
    updated_in_last_ndays: int
) -> dict:   
    filter = {
        K_NUM_WORDS_TITLE: {"$gte": config.filters.bean.min_title_len},
        K_GIST: {"$exists": True},
        K_CLUSTER_ID: {"$exists": True}
    }
    if kind: filter[K_KIND] = lower_case(kind)
    if sources: filter["$or"] = [
        {K_SOURCE: case_insensitive(sources)},
        {K_SHARED_IN: case_insensitive(sources)}
    ]
    if urls: filter[K_URL] = field_value(urls)
    if created_in_last_ndays: filter.update(created_in(created_in_last_ndays))
    if updated_in_last_ndays: filter.update(updated_in(updated_in_last_ndays))

    if isinstance(tags, str): filter[K_TAGS] = lower_case(tags)
    elif isinstance(tags, list):
        if all(isinstance(tag, str) for tag in tags): filter[K_TAGS] = lower_case(tags)
        elif any(isinstance(tag, list) for tag in tags): filter["$and"] = [{K_TAGS: lower_case(tag)} for tag in tags if tag] 
    
    return filter

def create_filter_for_generated_bean(
    page: Page,
    tags: str|list[str]|list[list[str]],
    created_in_last_ndays: int
) -> dict:   
    filter = {K_KIND: GENERATED}    
    if tags: filter[K_TAGS] = lower_case(tags)
    if page and page.query_tags: filter[K_TAGS] = lower_case(page.query_tags)
    if created_in_last_ndays: filter.update(created_in(created_in_last_ndays))
    return filter

@cached(max_size=CACHE_SIZE, ttl=ONE_HOUR)
def _embed(query: str):
    return embedder.embed_query(query)

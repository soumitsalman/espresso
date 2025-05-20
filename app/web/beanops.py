import re
import threading
from memoization import cached
from icecream import ic
from sentence_transformers import SentenceTransformer
from app.pybeansack.mongosack import LATEST_AND_TRENDING, NEWEST_AND_TRENDING
from app.pybeansack.models import *
from app.shared.utils import *
from app.shared.env import *

SORT_BY = {"Latest": NEWEST_AND_TRENDING, "Trending": LATEST_AND_TRENDING}

BEAN_HEADER_FIELDS = {K_URL: 1, K_TITLE: 1, K_KIND: 1, K_IMAGEURL: 1, K_SOURCE: 1, K_SITE_NAME: 1, K_CREATED: 1, K_LIKES: 1, K_COMMENTS: 1, K_SHARES: 1}
BEAN_BODY_FIELDS = {K_URL: 1, K_TAGS: 1, K_AUTHOR: 1}
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
def get_beans_for_home(tags: str|list[str], kinds: str|list[str], sources: str|list[str], last_ndays: int, sort_by, start: int, limit: int):
    """get one bean per cluster and per source"""
    filter = create_filter(tags, kinds, sources, None, last_ndays, None)
    return db.query_beans(filter, K_SOURCE, SORT_BY[sort_by], start, limit, BEAN_HEADER_FIELDS)

@cached(max_size=CACHE_SIZE, ttl=HALF_HOUR)
def get_beans_for_page(
    channel: Channel, 
    filter_tags: str|list[str], 
    filter_kinds: str|list[str], 
    filter_category: str, # only applicable if barista does not query_embedding
    sort_by, start: int, limit: int
):
    sort_by = SORT_BY[sort_by]
    filter=create_filter(
        kinds = filter_kinds or channel.query_kinds, 
        entities = [filter_tags, channel.query_tags], 
        sources = channel.query_sources, 
        urls = channel.query_urls,
        created_in_last_ndays = None, 
        updated_in_last_ndays = None
    )
    # if the barista is primarily based on specific urls, then just search for those
    if channel.query_urls: return db.query_beans(filter=filter, sort_by=sort_by, skip=start, limit=limit, project=BEAN_HEADER_FIELDS)
    if channel.query_embedding: return db.vector_search_beans(embedding=channel.query_embedding, similarity_score=channel.query_distance or config.filters.bean.default_accuracy, filter=filter, group_by=K_CLUSTER_ID, sort_by=sort_by, skip=start, limit=limit, project=BEAN_HEADER_FIELDS)
    if channel.query_tags or channel.query_sources: 
        if filter_category: return db.vector_search_beans(embedding=get_barista(filter_category, BARISTA_EMBEDDING_FIELDS).query_embedding, similarity_score=config.filters.bean.default_accuracy, filter=filter, group_by=K_CLUSTER_ID, sort_by=sort_by, skip=start, limit=limit, project=BEAN_HEADER_FIELDS)
        return db.query_beans(filter=filter, group_by=K_CLUSTER_ID, sort_by=sort_by, skip=start, limit=limit, project=BEAN_HEADER_FIELDS)   

@cached(max_size=CACHE_SIZE, ttl=FOUR_HOURS)
def get_filter_tags_for_page(barista: Channel, start: int, limit: int):
    # NOTE: no need for querying the urls separately since query tags are already there
    filter=create_filter(
        tags = barista.query_tags, 
        kinds = barista.query_kinds, 
        sources = barista.query_sources, 
        urls = barista.query_urls,
        created_in_last_ndays = None, 
        updated_in_last_ndays = None        
    )
    if barista.query_embedding: return db.vector_search_tags(embedding=barista.query_embedding, similarity_score=barista.query_distance or config.filters.bean.default_accuracy, filter=filter, skip=start, limit=limit)
    if barista.query_urls or barista.query_tags or barista.query_sources: return db.query_tags(filter=filter, exclude_from_result=barista.query_tags, skip=start, limit=limit)

@cached(max_size=CACHE_SIZE, ttl=HALF_HOUR)
def get_beans_for_source(source_id: str, tags: str|list[str]|list[list[str]], kinds: str|list[str], categories: str, last_ndays: int, sort_by, start: int, limit: int):
    """Retrieves news articles, social media posts, blog articles from the feed source"""  
    sort_by = SORT_BY[sort_by]
    filter=create_filter(tags, kinds, source_id, None, last_ndays, None)
    if categories: return db.vector_search_beans(embedding=get_barista(categories, BARISTA_EMBEDDING_FIELDS).query_embedding, similarity_score=config.filters.bean.default_accuracy, filter=filter, group_by=K_CLUSTER_ID, sort_by=sort_by, skip=start, limit=limit, project=BEAN_HEADER_FIELDS)
    return db.query_beans(filter=filter, group_by=K_CLUSTER_ID, sort_by=sort_by, skip=start, limit=limit, project=BEAN_HEADER_FIELDS)   

@cached(max_size=CACHE_SIZE, ttl=HALF_HOUR)
def search_beans(query: str, accuracy: float, tags: str|list[str]|list[list[str]], kinds: str|list[str], sources: str|list[str], last_ndays: int, sort_by, start: int, limit: int):
    """Searches and looks for news articles, social media posts, blog articles that match user interest, topic or query represented by `topic`."""  
    filter=create_filter(tags, kinds, sources, None, last_ndays, None)
    if is_valid_url(query): return db.vector_search_similar_beans(query, accuracy, filter, None, start, limit, BEAN_HEADER_FIELDS)
    if query: return db.vector_search_beans(embedding=embed_query(query), similarity_score=accuracy, filter=filter, skip=start, limit=limit, project=BEAN_HEADER_FIELDS)    
    if tags or sources: return db.query_beans(filter=filter, group_by=K_CLUSTER_ID, sort_by=SORT_BY.get(sort_by, NEWEST_AND_TRENDING), skip=start, limit=limit, project=BEAN_HEADER_FIELDS)
    # return []

# @cached(max_size=CACHE_SIZE, ttl=ONE_HOUR)
# def search_tags(query: str, accuracy: float, tags: str|list[str]|list[list[str]], kinds: str|list[str], sources: str|list[str], last_ndays: int, start: int, limit: int) -> list[Bean]:
#     if is_valid_url(query): 
#         bean = get_bean(query)
#         if not bean: return
#         filter=_create_filter(
#             tags=[tags, bean.tags], 
#             kinds=kinds, 
#             sources=sources, 
#             urls=None, 
#             created_in_last_ndays=last_ndays, 
#             updated_in_last_ndays=None
#         )  
#         return db.sample_vector_search_tags(embedding=bean.embedding, min_score=accuracy, filter=filter, skip=start, limit=limit)

#     filter=_create_filter(tags, kinds, sources, None, last_ndays, None)
#     if query: return db.sample_vector_search_tags(embedding=embed(query), min_score=accuracy, filter=filter, skip=start, limit=limit)  
#     return db.sample_query_tags(filter=filter, exclude_from_result=tags, skip=start, limit=limit)
    
@cached(max_size=CACHE_SIZE, ttl=ONE_HOUR)
def count_search_beans(query: str, accuracy: float, tags: str|list[str]|list[list[str]], kinds: str|list[str], sources: str|list[str], last_ndays: int, limit: int) -> int:
    filter=create_filter(tags, kinds, sources, None, last_ndays, None)
    if is_valid_url(query): return db.count_vector_search_similar_beans(query, accuracy, filter=filter, group_by=None, limit=limit)
    if query: return db.count_vector_search_beans(embedding=embed_query(query), similarity_score=accuracy, filter=filter, limit=limit)  
    if tags or sources: return db.count_beans(filter=filter, group_by=K_CLUSTER_ID, limit=limit)
    return 0
    
@cached(max_size=CACHE_SIZE, ttl=FOUR_HOURS)
def get_related(url: str, tags: str|list[str]|list[list[str]], kinds: str|list[str], sources: str|list[str], last_ndays: int):
    filter = create_filter(tags, kinds, sources, None, last_ndays, None)
    return db.query_related_beans(url=url, filter=filter, limit=config.filters.bean.max_related, project=BEAN_HEADER_FIELDS) 

BARISTA_MINIMAL_FIELDS = {K_ID: 1, K_TITLE: 1}
BARISTA_DEFAULT_FIELDS = {K_ID: 1, K_TITLE: 1, K_DESCRIPTION: 1, "public": 1, "owner": 1}
BARISTA_EMBEDDING_FIELDS = {K_ID: 1, K_EMBEDDING: 1}

@cached(max_size=CACHE_SIZE, ttl=ONE_HOUR)
def get_barista(id: str, project: dict = BARISTA_DEFAULT_FIELDS) -> Channel|None:
    barista = db.baristas.find_one(filter={K_ID: id}, projection=project)
    if barista: return Channel(**barista)

@cached(max_size=CACHE_SIZE, ttl=FOUR_HOURS)
def get_channels(ids: list[str], project: dict = BARISTA_DEFAULT_FIELDS) -> list[Channel]:
    if not ids: return
    result = db.baristas.find(
        filter={K_ID: {"$in": ids}}, 
        sort={K_TITLE: 1}, 
        projection=project
    )
    return [Channel(**barista) for barista in result]

# @cached(max_size=CACHE_SIZE, ttl=ONE_HOUR)
def get_following_baristas(user: User):
    pipeline = [
        {
            "$match": {K_ID: user.email}
        },
        {
            "$lookup": {
                "from": "baristas",
                "localField": "following",
                "foreignField": "_id",
                "as": "following"
            }
        },
        {
            "$unwind": "$following"
        },
        {
            "$project": {
                "_id": "$following._id",
                "title": "$following.title",
                "description": "$following.description",
                "public": "$following.public",
                "owner": "$following.owner"
            }
        },
        {
            "$sort": {K_TITLE: 1}
        }
    ]
    return [Channel(**barista) for barista in db.users.aggregate(pipeline)]

@cached(max_size=CACHE_SIZE, ttl=FOUR_HOURS)
def get_channel_suggestions(context: NavigationContext):
    return db.sample_baristas(5, BARISTA_DEFAULT_FIELDS)

@cached(max_size=CACHE_SIZE, ttl=HALF_HOUR)
def search_baristas(query: str):
    return db.search_baristas(query, BARISTA_DEFAULT_FIELDS)

def is_bookmarked(context: NavigationContext, url: str):
    if not context.is_registered: return False
    return db.is_bookmarked(context.user, url)

# create_projection = lambda with_content: FIELDS_WITH_CONTENT if with_content else FIELDS_WITHOUT_CONTENT
# convert_kind = lambda val: BLOG if val == "blogs" else NEWS
# field_value = lambda items: {"$in": items} if isinstance(items, list) else items
# lower_case = lambda items: {"$in": [item.lower() for item in items]} if isinstance(items, list) else items.lower()
# case_insensitive = lambda items: {"$in": [re.compile(item, re.IGNORECASE) for item in items]} if isinstance(items, list) else re.compile(items, re.IGNORECASE)

def create_filter(
    kind: str,
    categories: str|list[str], 
    entities: str|list[str], 
    regions: str|list[str],
    sources: str|list[str],
    urls: str|list[str],
    created_in_last_ndays: int,
    updated_in_last_ndays: int
) -> dict:   
    # pre process since they will all go to the tags filter
    tags = []
    if categories: tags.append({K_TAGS: lower_case(categories)})
    if entities: tags.append({K_TAGS: lower_case(entities)})
    if regions: tags.append({K_TAGS: lower_case(regions)})

    filter = {}
    if kind: filter[K_KIND] = kind
    if tags: filter["$and"] = tags
    if sources: filter["$or"] = [
        {K_SOURCE: case_insensitive(sources)},
        {K_SHARED_IN: case_insensitive(sources)}
    ]
    if urls: filter[K_URL] = field_value(urls)
    if created_in_last_ndays: filter[K_CREATED] = {"$gte": ndays_ago(created_in_last_ndays)}
    if updated_in_last_ndays: filter[K_UPDATED] = {"$gte": ndays_ago(updated_in_last_ndays)}  
    
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


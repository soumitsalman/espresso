import re
from icecream import ic
from app.pybeansack.mongosack import Beansack, NEWEST_AND_TRENDING
from app.pybeansack.models import *
from app.shared.utils import *
from app.shared.env import *
from app.shared.nlp import *
from llama_cpp import Llama
import threading

# PROJECTION = {K_EMBEDDING: 0, K_TEXT:0, K_ID: 0}
BEAN_FIELDS = {K_URL: 1, K_TITLE: 1, "gist": 1, "categories": 1, "entities": 1, K_SUMMARY: 1, K_KIND: 1, K_IMAGEURL: 1, K_AUTHOR: 1, K_SOURCE: 1, K_CREATED: 1}

db: Beansack = None

def initiatize(db_conn: str, db_name: str = "beansack", embedder_path: str = None):
    global db, embedder
    db = Beansack(db_conn, db_name)
    if embedder_path:
        embedder = Llama(model_path=embedder_path, n_ctx=512, n_threads=1, embedding=True, verbose=False)



def get_beans_per_group(tags: str|list[str], kinds: str|list[str], sources: str|list[str], last_ndays: int, sort_by, start: int, limit: int):
    """get one bean per cluster and per source"""
    sort_by = SORT_BY[sort_by]
    pipeline = [
        { "$match": create_filter(tags, kinds, sources, None, last_ndays, None) },
        { "$sort": sort_by },
        {
            "$group": {
                "_id": {
                    "cluster_id": "$cluster_id"
                },
                "source": { "$first": "$source" },
                "created": { "$first": "$created" },
                "updated": { "$first": "$updated" },
                "trend_score": { "$first": "$trend_score" },
                "doc": { "$first": "$$ROOT" }
                
            }
        },
        { "$sort": sort_by },
        {
            "$group": {
                "_id": {
                    "source": "$source"
                },
                "created": { "$first": "$created" },
                "updated": { "$first": "$updated" },
                "trend_score": { "$first": "$trend_score" },
                "doc": { "$first": "$doc" }
            }
        },
        { "$sort": sort_by },
        { "$skip": start },
        { "$limit": limit },
        { 
            "$project": {
                "_id": "$doc._id",
                "url": "$doc.url",
                "source": "$doc.source",
                "title": "$doc.title",
                "kind": "$doc.kind",
                "image_url": "$doc.image_url",
                "author": "$doc.author",
                "created": "$doc.created",
                "updated": "$doc.updated",
                "gist": "$doc.gist",
                "likes": "$doc.likes",
                "comments": "$doc.comments",
                "shares": "$doc.shares"
            }
        }
    ]
    return [Bean(**item) for item in db.beanstore.aggregate(pipeline)]

@cached(max_size=CACHE_SIZE, ttl=HALF_HOUR)
def get_barista_beans(
    barista: Channel, 
    filter_tags: str|list[str], 
    filter_kinds: str|list[str], 
    filter_topic: str, # only applicable if barista does not query_embedding
    sort_by, start: int, limit: int
):
    sort_by = SORT_BY[sort_by]
    filter=create_filter(
        tags = [filter_tags, barista.query_tags], 
        kinds = filter_kinds or barista.query_kinds, 
        sources = barista.query_sources, 
        urls = barista.query_urls,
        created_in_last_ndays = None, 
        updated_in_last_ndays = None
    )
    # if the barista is primarily based on specific urls, then just search for those
    if barista.query_urls: 
        return db.get_beans(filter=filter, sort_by=sort_by, skip=start, limit=limit, projection=BEAN_HEADER_FIELDS)
    if barista.query_embedding: 
        return db.vector_search_beans(embedding=barista.query_embedding, min_score=barista.query_distance or DEFAULT_ACCURACY, filter=filter, sort_by=sort_by, skip=start, limit=limit, projection=BEAN_HEADER_FIELDS)
    if barista.query_tags or barista.query_sources: 
        if filter_topic: 
            return db.vector_search_beans(embedding=get_barista(filter_topic, BARISTA_EMBEDDING_FIELDS).query_embedding, min_score=DEFAULT_ACCURACY, filter=filter, sort_by=sort_by, skip=start, limit=limit, projection=BEAN_HEADER_FIELDS)
        return db.query_beans_per_cluster(filter=filter, sort_by=sort_by, skip=start, limit=limit, projection=BEAN_HEADER_FIELDS)   
    return []

def get_beans_per_cluster(tags, kinds, sources, last_ndays, sort_by, start, limit):
    filter=create_filter(
        tags = tags, 
        kinds = kinds, 
        sources = sources, 
        urls=None,
        created_in_last_ndays = last_ndays, 
        updated_in_last_ndays = None
    )    
    projection = {"summary": 1}
    projection.update(BEAN_HEADER_FIELDS)
    return db.query_beans_per_cluster(filter=filter, sort_by=SORT_BY[sort_by], skip=start, limit=limit, projection=projection)

def get_barista_tags(barista: Channel, start: int, limit: int):
    # NOTE: no need for querying the urls separately since query tags are already there
    filter=create_filter(
        tags = barista.query_tags, 
        kinds = barista.query_kinds, 
        sources = barista.query_sources, 
        urls = barista.query_urls,
        created_in_last_ndays = None, 
        updated_in_last_ndays = None        
    )
    if barista.query_embedding: return db.sample_vector_search_tags(embedding=barista.query_embedding, min_score=barista.query_distance or DEFAULT_ACCURACY, filter=filter, skip=start, limit=limit)
    if barista.query_urls or barista.query_tags or barista.query_sources: return db.sample_query_tags(filter=filter, exclude_from_result=barista.query_tags, skip=start, limit=limit)

def get_feed_source_beans(feed_source: str, filter_tags: str|list[str]|list[list[str]], filter_kinds: str|list[str], filter_topic: str, last_ndays: int, sort_by, start: int, limit: int):
    """Retrieves news articles, social media posts, blog articles from the feed source"""  
    sort_by = SORT_BY[sort_by]
    filter=create_filter(filter_tags, filter_kinds, feed_source, None, last_ndays, None)
    if filter_topic: return db.vector_search_beans(embedding=get_barista(filter_topic, BARISTA_EMBEDDING_FIELDS).query_embedding, min_score=DEFAULT_ACCURACY, filter=filter, sort_by=sort_by, skip=start, limit=limit, projection=BEAN_HEADER_FIELDS)
    return db.query_beans_per_cluster(filter=filter, sort_by=sort_by, skip=start, limit=limit, projection=BEAN_HEADER_FIELDS)   

def search_beans(query: str, accuracy: float, tags: str|list[str]|list[list[str]], kinds: str|list[str], sources: str|list[str], last_ndays: int, sort_by, start: int, limit: int):
    """Searches and looks for news articles, social media posts, blog articles that match user interest, topic or query represented by `topic`."""  
    if is_valid_url(query): 
        bean = _get_bean(query)
        if not bean: return
        filter=create_filter(
            tags=[tags, bean.tags], 
            kinds=kinds, 
            sources=sources, 
            urls=None, 
            created_in_last_ndays=last_ndays, 
            updated_in_last_ndays=None
        )  
        return db.vector_search_beans(embedding=bean.embedding, min_score=accuracy, filter=filter, skip=start, limit=limit, projection=BEAN_HEADER_FIELDS)
    
    filter=create_filter(tags, kinds, sources, None, last_ndays, None)
    if query: return db.vector_search_beans(embedding=embed_query(query), min_score=accuracy, filter=filter, skip=start, limit=limit, projection=BEAN_HEADER_FIELDS)    
    if tags or sources: return db.query_beans_per_cluster(filter=filter, sort_by=SORT_BY.get(sort_by, NEWEST_AND_TRENDING), skip=start, limit=limit, projection=BEAN_HEADER_FIELDS)
    return []

def search_tags(query: str, accuracy: float, tags: str|list[str]|list[list[str]], kinds: str|list[str], sources: str|list[str], last_ndays: int, start: int, limit: int) -> list[Bean]:
    if is_valid_url(query): 
        bean = _get_bean(query)
        if not bean: return
        filter=create_filter(
            tags=[tags, bean.tags], 
            kinds=kinds, 
            sources=sources, 
            urls=None, 
            created_in_last_ndays=last_ndays, 
            updated_in_last_ndays=None
        )  
        return db.sample_vector_search_tags(embedding=bean.embedding, min_score=accuracy, filter=filter, skip=start, limit=limit)

    filter=create_filter(tags, kinds, sources, None, last_ndays, None)
    if query: return db.sample_vector_search_tags(embedding=embed_query(query), min_score=accuracy, filter=filter, skip=start, limit=limit)  
    return db.sample_query_tags(filter=filter, exclude_from_result=tags, skip=start, limit=limit)
    
def count_search_beans(query: str, accuracy: float, tags: str|list[str]|list[list[str]], kinds: str|list[str], sources: str|list[str], last_ndays: int, limit: int) -> int:
    if is_valid_url(query): 
        bean = _get_bean(query)
        if not bean: return
        filter=create_filter(
            tags=[tags, bean.tags], 
            kinds=kinds, 
            sources=sources, 
            urls=None, 
            created_in_last_ndays=last_ndays, 
            updated_in_last_ndays=None
        )  
        return db.count_vector_search_beans(embedding=bean.embedding, min_score=accuracy, filter=filter, limit=limit)

    filter=create_filter(tags, kinds, sources, None, last_ndays, None)
    if query: return db.count_vector_search_beans(embedding=embed_query(query), min_score=accuracy, filter=filter, limit=limit)  
    if tags or sources: return db.count_beans_per_cluster(filter=filter, limit=limit)
    return 0
    
def get_related(url: str, tags: str|list[str]|list[list[str]], kinds: str|list[str], sources: str|list[str], last_ndays: int, limit: int):
    filter = create_filter(tags, kinds, sources, None, last_ndays, None)
    return db.sample_related_beans(url=url, filter=filter, limit=limit) 

BARISTA_MINIMAL_FIELDS = {K_ID: 1, K_TITLE: 1}
BARISTA_DEFAULT_FIELDS = {K_ID: 1, K_TITLE: 1, K_DESCRIPTION: 1, "public": 1, "owner": 1}
BARISTA_EMBEDDING_FIELDS = {K_ID: 1, K_EMBEDDING: 1}

def get_barista(id: str, projection: dict = BARISTA_DEFAULT_FIELDS) -> Channel|None:
    barista = db.baristas.find_one(filter={K_ID: id}, projection=projection)
    if barista: return Channel(**barista)

def get_baristas(ids: list[str], projection: dict = BARISTA_DEFAULT_FIELDS) -> list[Channel]:
    if not ids: return
    result = db.baristas.find(
        filter={K_ID: {"$in": ids}}, 
        sort={K_TITLE: 1}, 
        projection=BARISTA_DEFAULT_FIELDS
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

def get_barista_recommendations(context: NavigationContext):
    return db.sample_baristas(5, BARISTA_DEFAULT_FIELDS)

def search_baristas(query: str):
    return db.search_baristas(query, BARISTA_DEFAULT_FIELDS)

def is_bookmarked(context: NavigationContext, url: str):
    if not context.is_registered: return False
    return db.is_bookmarked(context.user, url)

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

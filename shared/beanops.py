from icecream import ic
from pybeansack.beansack import *
from pybeansack.datamodels import *
from cachetools import TTLCache, cached

# cached for 8 hours
EIGHT_HOUR = 28000
ONE_DAY = 86400
ONE_WEEK = 604800
CACHE_SIZE = 1000

beansack: Beansack = None
PROJECTION = {K_EMBEDDING: 0, K_TEXT:0}

latest = lambda item: -item.updated

def initiatize(db_conn, embedder):
    global beansack
    # this is content retrieval (not processing). This does not need an llm in the beansack
    beansack=Beansack(db_conn, embedder)

@cached(TTLCache(maxsize=CACHE_SIZE, ttl=ONE_WEEK))
def get_sources():
    return beansack.get_sources()

@cached(TTLCache(maxsize=CACHE_SIZE, ttl=ONE_WEEK))
def get_content_types():
    return beansack.get_kinds()

@cached(TTLCache(maxsize=CACHE_SIZE, ttl=EIGHT_HOUR))
def get_beans_for_nugget(nugget_id, content_types: str|tuple[str], last_ndays: int, topn: int):
    return beansack.get_beans_by_nugget(nugget_id=nugget_id, filter=_create_filter(content_types, last_ndays), limit=topn, projection=PROJECTION) or []

@cached(TTLCache(maxsize=CACHE_SIZE, ttl=EIGHT_HOUR))
def count_beans_for_nugget(nugget_id, content_types: str|tuple[str], last_ndays: int, topn: int):
    return beansack.count_beans_by_nugget(nugget_id=nugget_id, filter=_create_filter(content_types, last_ndays), limit=topn)

@cached(TTLCache(maxsize=CACHE_SIZE, ttl=EIGHT_HOUR))
def highlights(query, last_ndays: int, topn: int):
    """Retrieves the trending news highlights that match user interest, topic or query."""
    return _retrieve_queries(query, lambda q: beansack.trending_nuggets(query=q, filter=timewindow_filter(last_ndays), limit=topn, projection=PROJECTION))
    
@cached(TTLCache(maxsize=CACHE_SIZE, ttl=EIGHT_HOUR))
def trending(query, content_types: str|tuple[str], last_ndays: int, topn: int):
    """Retrieves the trending news articles, social media posts, blog articles that match user interest, topic or query."""
    return _retrieve_queries(query, lambda q: beansack.trending_beans(query=q, filter=_create_filter(content_types, last_ndays), limit=topn, projection=PROJECTION))
    
@cached(TTLCache(maxsize=CACHE_SIZE, ttl=EIGHT_HOUR))
def search(query: str, content_types: str|tuple[str], last_ndays: int, topn: int):
    """Searches and looks for news articles, social media posts, blog articles that match user interest, topic or query represented by `topic`."""
    return _retrieve_queries(query, lambda q: beansack.search_beans(query=q, filter=_create_filter(content_types, last_ndays), limit=topn, sort_by=LATEST, projection=PROJECTION))

@cached(TTLCache(maxsize=CACHE_SIZE, ttl=EIGHT_HOUR))
def search_all(query: str, last_ndays: int, topn: int):
    """Searches and looks for news articles, social media posts, blog articles that match user interest, topic or query represented by `topic`."""
    filter = timewindow_filter(last_ndays)
    return _retrieve_queries(query, lambda q: beansack.search_beans(query=q, filter=filter, limit=topn, sort_by=LATEST, projection=PROJECTION)) \
        + _retrieve_queries(query, lambda q: beansack.search_nuggets(query=q, filter=filter, limit=topn, sort_by=LATEST, projection=PROJECTION))

def _retrieve_queries(query_items, retrieval_func):
    query_items = query_items if isinstance(query_items, list) else [query_items]
    results = []
    for q in query_items:
        nugs = retrieval_func(q)
        if nugs:
            results.extend(nugs)
    return results
        
def _create_filter(content_types: str|tuple[str], last_ndays: int):
    filter = timewindow_filter(last_ndays)
    if isinstance(content_types, str):
        filter.update({K_KIND: content_types})
    elif isinstance(content_types, (tuple, list)):
        filter.update({K_KIND: { "$in": list(content_types) } })
    return filter



# import requests
# from retry import retry
# from . import config

# _RETRIEVE_BEANS = "/beans"
# _SEARCH_BEANS = "/beans/search"
# _TRENDING_BEANS = "/beans/trending"
# _TRENDING_NUGGETS = "/nuggets/trending"

# def retrieve_beans(urls: list, kinds: list[str] = None, window:int = None, limit:int = None):
#     return retry_coffemaker(_RETRIEVE_BEANS, 
#                             _make_params(window=window, limit=limit, kinds=kinds), 
#                             _make_body(urls = urls))

# def search_beans(nugget: str = None, categories = None, search_text: str = None, kinds:list[str] = None, window: int = None, limit: int = None):
#     return retry_coffemaker(_SEARCH_BEANS, 
#                             _make_params(window=window, limit=limit, kinds=kinds), 
#                             _make_body(nugget=nugget, categories=categories, search_text=search_text))

# def trending_beans(nugget = None, categories = None, search_text: str = None, kinds:list[str] = None, window: int = None, limit: int = None):
#     return retry_coffemaker(_TRENDING_BEANS, 
#                             _make_params(window=window, limit=limit, kinds=kinds), 
#                             _make_body(nugget=nugget, categories=categories, search_text=search_text))

# def trending_nuggets(categories, window, limit):    
#     return retry_coffemaker(_TRENDING_NUGGETS, 
#                             _make_params(window=window, limit=limit), 
#                             _make_body(categories=categories))

# # this is same as trending_beans but it returns result bucketed per topic
# # topics has to be an list of dict where each element should be { "text": str, "embeddings": list[float] }
# def trending_beans_by_topics(topics: list, kinds, window, limit):
#     return { topic["text"]: trending_beans(categories=topic["embeddings"], kinds=kinds, window=window, limit=limit) for topic in topics }

# # this is same as trending_nuggets but it returns result bucketed per topic
# # topics has to be an list of dict where each element should be { "text": str, "embeddings": list[float] }
# def trending_nuggets_by_topics(topics: list, window, limit):
#     return { topic["text"]: trending_nuggets(topic["embeddings"], window, limit) for topic in topics }

# def _make_params(window = None, limit = None, kinds = None, source=None):
#     params = {}
#     if window:
#         params["window"]=window
#     if kinds:
#         params["kind"]=kinds
#     if limit:
#         params["topn"]=limit
#     if source:
#         params["source"]=source
#     return params if len(params)>0 else None

# def _make_body(nugget = None, categories = None, search_text = None, urls = None):
#     body = {}
#     if nugget:        
#         body["nuggets"] = [nugget]
    
#     if categories:
#         if isinstance(categories, str):
#             # this is a single item of text
#             body["categories"] = [categories]
#         elif isinstance(categories, list) and isinstance(categories[0], float):
#             # this is a single item of embeddings
#             body["embeddings"] = [categories]
#         elif isinstance(categories, list) and isinstance(categories[0], str):
#             # this is list of text
#             body["categories"] = categories
#         elif isinstance(categories, list) and isinstance(categories[0], list):
#             # this is a list of embeddings
#             body["embeddings"] = categories
    
#     if search_text:
#         body["context"] = search_text

#     if urls:
#         body["urls"] = urls
    
#     return body if len(body) > 0 else None
    
# @retry(requests.HTTPError, tries=5, delay=5)
# def _retry_internal(path, params, body):
#     resp = requests.get(config.get_coffeemaker_url(path), params=params, json=body)
#     resp.raise_for_status()
#     return resp.json() if (resp.status_code == requests.codes["ok"]) else None

# def retry_coffemaker(path, params, body):    
#     try:
#         return _retry_internal(path, params, body)
#     except:
#         return None
    
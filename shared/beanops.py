import requests
from retry import retry
from . import config

_RETRIEVE_BEANS = "/beans"
_SEARCH_BEANS = "/beans/search"
_TRENDING_BEANS = "/beans/trending"
_TRENDING_NUGGETS = "/nuggets/trending"

def retrieve_beans(urls: list, kinds: list[str] = None, window:int = None, limit:int = None):
    return retry_coffemaker(_RETRIEVE_BEANS, 
                            _make_params(window=window, limit=limit, kinds=kinds), 
                            _make_body(urls = urls))

def search_beans(nugget: str = None, categories = None, search_text: str = None, kinds:list[str] = None, window: int = None, limit: int = None):
    return retry_coffemaker(_SEARCH_BEANS, 
                            _make_params(window=window, limit=limit, kinds=kinds), 
                            _make_body(nugget=nugget, categories=categories, search_text=search_text))

def trending_beans(nugget = None, categories = None, search_text: str = None, kinds:list[str] = None, window: int = None, limit: int = None):
    return retry_coffemaker(_TRENDING_BEANS, 
                            _make_params(window=window, limit=limit, kinds=kinds), 
                            _make_body(nugget=nugget, categories=categories, search_text=search_text))

def trending_nuggets(categories, window, limit):    
    return retry_coffemaker(_TRENDING_NUGGETS, 
                            _make_params(window=window, limit=limit), 
                            _make_body(categories=categories))

# this is same as trending_beans but it returns result bucketed per topic
# topics has to be an list of dict where each element should be { "text": str, "embeddings": list[float] }
def trending_beans_by_topics(topics: list, kinds, window, limit):
    return { topic["text"]: trending_beans(categories=topic["embeddings"], kinds=kinds, window=window, limit=limit) for topic in topics }

# this is same as trending_nuggets but it returns result bucketed per topic
# topics has to be an list of dict where each element should be { "text": str, "embeddings": list[float] }
def trending_nuggets_by_topics(topics: list, window, limit):
    return { topic["text"]: trending_nuggets(topic["embeddings"], window, limit) for topic in topics }

def _make_params(window = None, limit = None, kinds = None, source=None):
    params = {}
    if window:
        params["window"]=window
    if kinds:
        params["kind"]=kinds
    if limit:
        params["topn"]=limit
    if source:
        params["source"]=source
    return params if len(params)>0 else None

def _make_body(nugget = None, categories = None, search_text = None, urls = None):
    body = {}
    if nugget:        
        body["nuggets"] = [nugget]
    
    if categories:
        if isinstance(categories, str):
            # this is a single item of text
            body["categories"] = [categories]
        elif isinstance(categories, list) and isinstance(categories[0], float):
            # this is a single item of embeddings
            body["embeddings"] = [categories]
        elif isinstance(categories, list) and isinstance(categories[0], str):
            # this is list of text
            body["categories"] = categories
        elif isinstance(categories, list) and isinstance(categories[0], list):
            # this is a list of embeddings
            body["embeddings"] = categories
    
    if search_text:
        body["context"] = search_text

    if urls:
        body["urls"] = urls
    
    return body if len(body) > 0 else None
    
@retry(requests.HTTPError, tries=5, delay=5)
def _retry_internal(path, params, body):
    resp = requests.get(config.get_coffeemaker_url(path), params=params, json=body)
    resp.raise_for_status()
    return resp.json() if (resp.status_code == requests.codes["ok"]) else None

def retry_coffemaker(path, params, body):    
    try:
        return _retry_internal(path, params, body)
    except:
        return None
    
############################
## BEANSACK DB OPERATIONS ##
############################

from datetime import datetime, timedelta
from functools import reduce
import logging
import operator
from .embedding import *
from .datamodels import *
from bson import InvalidBSON
from pymongo import MongoClient, UpdateMany, UpdateOne
from pymongo import MongoClient, UpdateMany, UpdateOne
from pymongo.collection import Collection
from icecream import ic

TIMEOUT = 300000 # 3 mins

# names of db and collections
BEANSACK = "beansack"
BEANS = "beans"
CHATTERS = "chatters"
SOURCES = "sources"

DEFAULT_VECTOR_SEARCH_SCORE = 0.73
DEFAULT_VECTOR_LIMIT = 100

TRENDING = {K_TRENDSCORE: -1}
LATEST = {K_UPDATED: -1}
NEWEST = {K_CREATED: -1}
TRENDING_AND_LATEST = {K_TRENDSCORE: -1, K_UPDATED: -1}
LATEST_AND_TRENDING = {K_UPDATED: -1, K_TRENDSCORE: -1}
NEWEST_AND_TRENDING = {K_CREATED: -1, K_TRENDSCORE: -1}

class Beansack:
    beanstore: Collection
    chatterstore: Collection
    sourcestore: Collection
    embedder: Embeddings    

    def __init__(self, conn_str: str, embedder: Embeddings = None):   
             
        client = MongoClient(
            conn_str, 
            appname="PyCoffeemaker_or_Espresso", 
            timeoutMS=TIMEOUT,
            serverSelectionTimeoutMS=TIMEOUT,
            socketTimeoutMS=TIMEOUT,
            connectTimeoutMS=TIMEOUT,
            retryWrites=True)        
        self.beanstore: Collection = client[BEANSACK][BEANS]
        self.chatterstore: Collection = client[BEANSACK][CHATTERS]        
        self.sourcestore: Collection = client[BEANSACK][SOURCES]  
        self.embedder: Embeddings = embedder

    ##########################
    ## STORING AND INDEXING ##
    ##########################
    def store_beans(self, beans: list[Bean]) -> int:   
        if beans:
            beans = self._rectify_as_needed(beans) 
            res = self.beanstore.insert_many([bean.model_dump(exclude_unset=True, exclude_none=True, by_alias=True) for bean in beans], ordered=False)            
            return len(res.inserted_ids)
        return 0

    def filter_unstored_beans(self, beans: list[Bean]):
        exists = [item[K_URL] for item in self.beanstore.find({K_URL: {"$in": [bean.url for bean in beans]}}, {K_URL: 1})]
        return list({bean.url: bean for bean in beans if (bean.url not in exists)}.values())
        
    # this function checks for embeddings, updated time and any other rectification needed before inserting
    def _rectify_as_needed(self, items: list[Bean|Highlight]):
        # for each item if there is no embedding and create one from the text.
        batch_time = int(datetime.now().timestamp())
        for item in items:
            if not item.embedding and self.embedder:
                item.embedding = self.embedder.embed(item.digest())
            if not item.updated:
                item.updated = batch_time
        return items

    def store_chatters(self, chatters: list[Chatter]):
        if chatters:
            res = self.chatterstore.insert_many([item.model_dump(exclude_unset=True, exclude_none=True, by_alias=True) for item in chatters])
            return len(res.inserted_ids or [])

    # TODO: enable later. this is temporarily disabled
    # def update_beans(self, urls: list[str|list[str]], updates: list[dict]) -> int:
    #     # if update is a single dict then it will apply to all beans with the specified urls
    #     # or else update is a list of equal length, and we will do a bulk_write of update one
    #     if len(urls) != len(updates):
    #         logger.warning("Bulk update discrepency: len(urls) [%d] != len(updates) [%d]", len(urls), len(updates))
        
    #     makeupdate = lambda filter, set_fields: UpdateOne({K_URL: filter}, set_fields) if isinstance(filter, str) else UpdateMany({K_URL: {"$in": filter}}, set_fields)       
    #     writes = list(map(makeupdate, urls, [{"$set": fields} for fields in updates]))
    #     return self.beanstore.bulk_write(writes).modified_count
      
    def delete_old(self, window: int):
        time_filter = {K_UPDATED: { "$lt": get_timevalue(window) }}
        bean_count = self.beanstore.delete_many(time_filter).deleted_count
        chatter_count = self.chatterstore.delete_many(time_filter).deleted_count
        return (bean_count, chatter_count)

    ####################
    ## GET AND SEARCH ##
    ####################

    def get_beans(self, filter, sort_by = None, skip = None, limit = None,  projection = None) -> list[Bean]:
        cursor = self.beanstore.find(filter = filter, projection = projection, sort=sort_by, skip = skip, limit=limit)
        return _deserialize_beans(cursor)

    def vector_search_beans(self, 
            query: str = None,
            embedding: list[float] = None, 
            min_score = DEFAULT_VECTOR_SEARCH_SCORE, 
            filter = None, 
            sort_by = None,
            skip = None,
            limit = DEFAULT_VECTOR_LIMIT, 
            projection = None
        ) -> list[Bean]:
        pipline = self._vector_search_pipeline(query, embedding, min_score, filter, sort_by, skip, limit, projection)
        return _deserialize_beans(self.beanstore.aggregate(pipeline=pipline))
    
    def count_vector_search_beans(self, query: str = None, embedding: list[float] = None, min_score = DEFAULT_VECTOR_SEARCH_SCORE, filter: dict = None, limit = DEFAULT_VECTOR_LIMIT) -> int:
        pipeline = self._count_vector_search_pipeline(query, embedding, min_score, filter, limit)
        result = list(self.beanstore.aggregate(pipeline))
        return result[0]['total_count'] if result else 0
    
    def text_search_beans(self, query: str, filter = None, sort_by = None, skip=None, limit=None, projection=None):
        return _deserialize_beans(
            self.beanstore.aggregate(
                self._text_search_pipeline(query, filter=filter, sort_by=sort_by, skip=skip, limit=limit, projection=projection, for_count=False)))
    
    def count_text_search_beans(self, query: str, filter = None, limit = None):
        result = self.beanstore.aggregate(self._text_search_pipeline(query, filter=filter, sort_by=None, skip=0, limit=limit, projection=None, for_count=True))
        return next(iter(result))['total_count'] if result else 0
    
    def get_unique_beans(self, filter, sort_by = None, skip = 0, limit = None, projection = None):
        pipeline = self._unique_beans_pipeline(filter, sort_by=sort_by, skip=skip, limit=limit, projection=projection, for_count=False)
        return _deserialize_beans(self.beanstore.aggregate(pipeline))
    
    def count_unique_beans(self, filter, limit = None):
        pipeline = self._unique_beans_pipeline(filter, sort_by=None, skip=None, limit=limit, projection=None, for_count=True)
        result = self.beanstore.aggregate(pipeline)
        return next(iter(result))['total_count'] if result else 0
    
    def get_trending_tags(self, filter, skip = None, limit = None):
        match_filter = {K_TAGS: {"$exists": True}}
        if filter:
            match_filter.update(filter)
        pipeline = [
            {"$match": match_filter},
            {"$unwind": "$tags"}, 
            {
                "$group": {
                    "_id": "$tags",
                    "cluster_id": {"$first": "$cluster_id"},
                    "trend_score": { "$sum": "$trend_score" },
                    "updated": { "$max": "$updated" }
                }
            },
            {
                "$sort": TRENDING
            },
            {
                "$group": {
                    "_id": "$cluster_id",
                    "url": {"$first": "$cluster_id"},
                    "tags": { "$first": "$_id" },
                    "trend_score": { "$first": "$trend_score" },
                    "updated": { "$first": "$updated" }
                }
            },
            {"$sort": LATEST_AND_TRENDING}
        ]
        if skip:
            pipeline.append({"$skip": skip})    
        if limit:
            pipeline.append({"$limit": limit})   
        return _deserialize_beans(self.beanstore.aggregate(pipeline))
  
    def count_related_beans(self, urls: list[str]) -> dict:
        pipeline = [            
            {
                "$group": {
                    "_id": "$cluster_id",
                    "cluster_id": {"$first": "$cluster_id"},            
                    "urls": {"$addToSet": "$url"},
                    "count": {"$sum": 1}
                }        
            },
            {
                "$unwind": "$urls"
            },
            {
                "$match": {"urls": {"$in": urls}}
            },            
            {
                "$project": {
                    "_id": 0,
                    "cluster_id": "$cluster_id",
                    "url": "$urls",
                    "cluster_size": "$count"
                }
            }
        ]    
        return [item for item in self.beanstore.aggregate(pipeline)]
    
    def _unique_beans_pipeline(self, filter, sort_by, skip, limit, projection, for_count):
        pipeline = []
        if filter:
            pipeline.append({"$match": filter})
        if sort_by:
            pipeline.append({"$sort": sort_by})        
        pipeline.append({
            "$group": {
                "_id": "$cluster_id",
                K_CLUSTER_ID: {"$first": "$cluster_id"},
                K_URL: {"$first": "$url"},
                K_TITLE: {"$first": "$title"},
                K_SUMMARY: {"$first": "$summary"},
                K_HIGHLIGHTS: {"$first": "$highlights"},
                K_TAGS: {"$first": "$tags"},
                K_CATEGORIES: {"$first": "$categories"},
                K_SOURCE: {"$first": "$source"},
                K_CHANNEL: {"$first": "$channel"},
                K_UPDATED: {"$first": "$updated"},
                K_CREATED: {"$first": "$created"},
                K_LIKES: {"$first": "$likes"},
                K_COMMENTS: {"$first": "$comments"},
                K_TRENDSCORE: {"$first": "$trend_score"},
                K_AUTHOR: {"$first": "$author"},
                K_KIND: {"$first": "$kind"},
                K_IMAGEURL: {"$first": "$image_url"}
            }
        })
        if sort_by:
            pipeline.append({"$sort": sort_by})
        if skip:
            pipeline.append({"$skip": skip})
        if limit:
            pipeline.append({"$limit": limit})
        if for_count:
            pipeline.append({"$count": "total_count"})
        if projection:
            pipeline.append({"$project": projection})
        return pipeline

    def _text_search_pipeline(self, text: str, filter, sort_by, skip, limit, projection, for_count):
        match = {"$text": {"$search": text}}
        if filter:
            match.update(filter)

        pipeline = [
            {   "$match": match },            
            {   "$addFields":  {"search_score": {"$meta": "textScore"}} },
            {   "$match": { "search_score": {"$gte": len(text.split(sep=" ,.;:`'\"\n\t\r\f"))}} }  # this is hueristic to count the number of word match
        ]        

        if not for_count:
            sort = {"search_score": -1}
            if sort_by:
                sort.update(sort_by)
            pipeline.append({"$sort": sort})

        if skip:
            pipeline.append({"$skip": skip})
        if limit:
            pipeline.append({"$limit": limit})
        if for_count:
            pipeline.append({"$count": "total_count"})
        if not for_count and projection:
            pipeline.append({"$project": projection})
        return pipeline
   
    def _vector_search_pipeline(self, text, embedding, min_score, filter, sort_by, skip, limit, projection):        
        pipeline = [            
            {
                "$search": {
                    "cosmosSearch": {
                        "vector": embedding or self.embedder.embed_query(text),
                        "path":   K_EMBEDDING,
                        "filter": filter or {},
                        "k":      limit,
                    },
                    "returnStoredSource": True
                }
            },
            {
                "$addFields": { "search_score": {"$meta": "searchScore"} }
            },
            {
                "$match": { "search_score": {"$gte": min_score} }
            }
        ]           
        if sort_by:
            pipeline.append({"$sort": sort_by})
        if skip:
            pipeline.append({"$skip": skip})
        if limit:
            pipeline.append({"$limit": limit})
        if projection:
            pipeline.append({"$project": projection})
        return pipeline
    
    def _count_vector_search_pipeline(self, text, embedding, min_score, filter, limit):
        pipline = self._vector_search_pipeline(text, embedding, min_score, filter, limit, None, None)
        pipline.append({ "$count": "total_count"})
        return pipline
    
    def get_chatter_stats(self, urls: str|list[str]) -> list[Chatter]:
        """Retrieves the latest social media status from different mediums."""
        pipeline = self._chatter_stats_pipeline(urls)
        return _deserialize_chatters(self.chatterstore.aggregate(pipeline))
        
    def get_consolidated_chatter_stats(self, urls: list[str]) -> list[Chatter]:
        pipeline = self._chatter_stats_pipeline(urls) + [            
            {
                "$group": {
                    "_id":           "$url",
                    "url":           {"$first": "$url"},                    
                    "likes":         {"$sum": "$likes"},
                    "comments":      {"$sum": "$comments"}
                }
            }
        ]
        return _deserialize_chatters(self.chatterstore.aggregate(pipeline))
    
    def _chatter_stats_pipeline(self, urls: list[str]):
        return [
            {
                "$match": { K_URL: {"$in": urls} if isinstance(urls, list) else urls }
            },
            {
                "$sort": {K_UPDATED: -1}
            },
            {
                "$group": {
                    "_id": {
                        "url": "$url",
                        "container_url": "$container_url"
                    },
                    K_URL:           {"$first": "$url"},
                    K_UPDATED:       {"$first": "$updated"},                
                    K_SOURCE:        {"$first": "$source"},
                    K_CHANNEL:       {"$first": "$channel"},
                    K_CONTAINER_URL: {"$first": "$container_url"},
                    K_LIKES:         {"$first": "$likes"},
                    K_COMMENTS:      {"$first": "$comments"}                
                }
            }
        ]

## local utilities for pymongo
def _deserialize_beans(cursor) -> list[Bean]:
    try:
        return [Bean(**item) for item in cursor]
    except:
        _get_logger().error("failed deserializing beans")
        return []

def _deserialize_chatters(cursor) -> list[Chatter]:
    try:
        return [Chatter(**item) for item in cursor]
    except:
        _get_logger().error("failed deserializing chatters")
        return []
    
def _get_logger():
    return logging.getLogger("beansack")

def updated_in(last_ndays: int):
    return {K_UPDATED: {"$gte": get_timevalue(last_ndays)}}

def created_in(last_ndays: int):
    return {K_CREATED: {"$gte": get_timevalue(last_ndays)}}

def get_timevalue(last_ndays: int):
    return int((datetime.now() - timedelta(days=last_ndays)).timestamp())


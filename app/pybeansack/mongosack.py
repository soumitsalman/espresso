############################
## BEANSACK DB OPERATIONS ##
############################
import os
from datetime import datetime, timedelta, timezone
from functools import reduce
import logging
from bson import SON
from icecream import ic
from .models import *
from pymongo import MongoClient, UpdateMany, UpdateOne
from pymongo.collection import Collection

TIMEOUT = 300000 # 3 mins
DEFAULT_VECTOR_SEARCH_SCORE = 0.7
DEFAULT_VECTOR_SEARCH_LIMIT = 500
MAX_CLUSTER_SIZE = 20 # this is kept as a multiplier to optimize search

# names of db and collections
BEANS = "beans"
CHATTERS = "chatters"
SOURCES = "sources"

CLUSTER_GROUP = {
    K_ID: "$cluster_id",
    K_CLUSTER_ID: {"$first": "$cluster_id"},
    K_URL: {"$first": "$url"},
    K_TITLE: {"$first": "$title"},
    "gist": {"$first": "$gist"},
    K_SUMMARY: {"$first": "$summary"},
    K_TAGS: {"$first": "$tags"},
    K_CATEGORIES: {"$first": "$categories"},
    K_SOURCE: {"$first": "$source"},
    K_UPDATED: {"$first": "$updated"},
    K_CREATED: {"$first": "$created"},
    K_LIKES: {"$first": "$likes"},
    K_COMMENTS: {"$first": "$comments"},
    K_SHARES: {"$first": "$shares"},
    K_SEARCH_SCORE: {"$first": "$search_score"},
    K_TRENDSCORE: {"$first": "$trend_score"},
    K_AUTHOR: {"$first": "$author"},
    K_KIND: {"$first": "$kind"},
    K_IMAGEURL: {"$first": "$image_url"}
}

TRENDING = {K_TRENDSCORE: -1}
LATEST = {K_UPDATED: -1}
NEWEST = {K_CREATED: -1}
NEWEST_AND_TRENDING = SON([(K_CREATED, -1), (K_TRENDSCORE, -1)])
LATEST_AND_TRENDING = SON([(K_UPDATED, -1), (K_TRENDSCORE, -1)])

now = datetime.now
ndays_ago = lambda ndays: now() - timedelta(days=ndays)
log = logging.getLogger(__name__)

class Beansack:
    beanstore: Collection
    chatterstore: Collection
    sourcestore: Collection
    users: Collection
    baristas: Collection

    def __init__(self, 
        conn_str: str = os.getenv("REMOTE_DB_CONNECTION_STRING", "mongodb://localhost:27017"), 
        db_name: str = os.getenv("DB_NAME", "beansack")
    ):  
        client = MongoClient(
            conn_str, 
            timeoutMS=TIMEOUT,
            serverSelectionTimeoutMS=TIMEOUT,
            socketTimeoutMS=TIMEOUT,
            connectTimeoutMS=TIMEOUT,
            retryWrites=True,
            minPoolSize=10,
            maxPoolSize=100)        
        self.beanstore: Collection = client[db_name][BEANS]
        self.chatterstore: Collection = client[db_name][CHATTERS]        
        self.sourcestore: Collection = client[db_name][SOURCES]  
        self.users = client[db_name]["users"]
        self.baristas = client[db_name]["baristas"]

    ###################
    ## BEANS STORING ##
    ###################
    def store_beans(self, beans: list[Bean]) -> int:   
        beans = self.not_exists(beans)
        if not beans: return 0

        res = self.beanstore.insert_many([bean.model_dump(exclude_unset=True, exclude_none=True, by_alias=True) for bean in beans], ordered=False)            
        return len(res.inserted_ids)

    def not_exists(self, beans: list[Bean]):
        if not beans: return beans

        exists = [item[K_URL] for item in self.beanstore.find({K_URL: {"$in": [bean.url for bean in beans]}}, {K_URL: 1})]
        return list({bean.url: bean for bean in beans if (bean.url not in exists)}.values())
                
    def store_chatters(self, chatters: list[Chatter]):
        if not chatters: return chatters

        res = self.chatterstore.insert_many([item.model_dump(exclude_unset=True, exclude_none=True, by_alias=True) for item in chatters])
        return len(res.inserted_ids or [])

    def update_beans(self, updates):
        return self.beanstore.bulk_write(updates, ordered=False, bypass_document_validation=True).matched_count
      
    def delete_old(self, window: int):
        time_filter = {K_UPDATED: { "$lt": ndays_ago(window) }}
        return self.beanstore.delete_many(time_filter).deleted_count
        # TODO: add delete for bookmarked bean

    ################################
    ## BEANS RETRIEVAL AND SEARCH ##
    ################################
    def get_beans(self, filter, sort_by = None, skip = 0, limit = 0,  projection = None) -> list[Bean]:
        cursor = self.beanstore.find(filter = filter, projection = projection, sort=sort_by, skip = skip, limit=limit)
        return _deserialize_beans(cursor)
    
    def sample_related_beans(self, url: str, filter: dict = None, limit: int = 0) -> list[Bean]:
        match_filter = {K_ID: url}
        if filter:
            match_filter.update(filter)
        pipeline = [
            { 
                "$match": match_filter 
            },
            {
                "$lookup": {
                    "from": "beans",
                    "localField": "cluster_id",
                    "foreignField": "cluster_id",
                    "as": "related_beans"
                }
            },
            {
                "$unwind": "$related_beans"
            },
            { 
                "$sample": {"size": limit+1} 
            },
            {
                "$match": {
                    "related_beans._id": {"$ne": url}
                }
            },
            {
                "$project": {
                    "_id": "$related_beans._id",
                    "url": "$related_beans.url",
                    "source": "$related_beans.source",
                    "title": "$related_beans.title",
                    "gist": "$related_beans.gist",
                    "kind": "$related_beans.kind",
                    "image_url": "$related_beans.image_url",
                    "author": "$related_beans.author",
                    "created": "$related_beans.created",
                    "collected": "$related_beans.collected",
                    "updated": "$related_beans.updated",
                    "tags": "$related_beans.tags",
                    "summary": "$related_beans.summary",
                    "cluster_id": "$related_beans.cluster_id",
                    "likes": "$related_beans.likes",
                    "comments": "$related_beans.comments",
                    "shares": "$related_beans.shares"
                }
            },
            { "$sort": NEWEST_AND_TRENDING }
        ]
        return _deserialize_beans(self.beanstore.aggregate(pipeline))

    def vector_search_beans(self, 
            embedding: list[float] = None, 
            min_score = None, 
            filter = None, 
            sort_by = None,
            skip = 0,
            limit = 0, 
            projection = None
        ) -> list[Bean]:
        pipline = self._vector_search_pipeline(embedding, min_score, filter, sort_by, skip, limit, projection)
        return _deserialize_beans(self.beanstore.aggregate(pipeline=pipline))
    
    def count_vector_search_beans(self, embedding: list[float] = None, min_score = None, filter: dict = None, limit = 0) -> int:
        pipeline = self._count_vector_search_pipeline(embedding, min_score, filter, limit)
        result = list(self.beanstore.aggregate(pipeline))
        return result[0]['total_count'] if result else 0
    
    def text_search_beans(self, query: str, filter = None, sort_by = None, skip=0, limit=0, projection=None):
        pipeline = self._text_search_pipeline(query, filter, sort_by, skip, limit, projection, for_count=False)
        return _deserialize_beans(self.beanstore.aggregate(pipeline=pipeline))
    
    def count_text_search_beans(self, query: str, filter = None, limit = 0):
        result = self.beanstore.aggregate(self._text_search_pipeline(query, filter=filter, sort_by=None, skip=0, limit=limit, projection=None, for_count=True))
        return next(iter(result), {'total_count': 0})['total_count'] if result else 0
    
    def query_beans_per_cluster(self, filter, sort_by = None, skip = 0, limit = 0, projection = None):
        pipeline = self._query_beans_pipeline(filter, sort_by=sort_by, skip=skip, limit=limit, projection=projection, for_count=False)
        return _deserialize_beans(self.beanstore.aggregate(pipeline))
    
    def count_beans_per_cluster(self, filter, limit = 0):
        pipeline = self._query_beans_pipeline(filter, sort_by=None, skip=0, limit=limit, projection=None, for_count=True)
        result = self.beanstore.aggregate(pipeline)
        return next(iter(result), {'total_count': 0})['total_count'] if result else 0
    
    def sample_query_tags(self, filter, exclude_from_result = None, skip = 0, limit = 0):
        match = {K_TAGS: {"$exists": True}}
        if filter: match.update(filter)
        # flatten the tags within the filter
        # take the ones that show up the most
        # sort by the number of times the tags appear
        pipeline = [
            { "$match": filter },
            { "$unwind": "$tags" },
            {
                "$group": {
                    "_id": "$tags",
                    "count": { "$sum": 1 }
                }
            },
            { "$sort": {"count": -1} }
        ]
        if exclude_from_result:
            pipeline.append({"$match": {"_id": {"$nin": exclude_from_result}}})
        if skip:
            pipeline.append({"$skip": skip})    
        if limit:
            pipeline.append({"$limit": 3*limit})
            pipeline.append({"$sample": {"size": limit}})   
        return [item[K_ID] for item in self.beanstore.aggregate(pipeline=pipeline)]
    
    def sample_text_search_tags(self, query: str, filter = None, skip = 0, limit = 0):
        match = {"$text": {"$search": query}}
        if filter: match.update(filter)
        pipeline = [
            { "$match": match },
            { "$unwind": "$tags" },
            { 
                "$group": { 
                    "_id": "$tags", 
                    "count": { "$sum": 1 } 
                } 
            },
            { "$sort": {"count": -1} }
        ]
        if skip:
            pipeline.append({"$skip": skip})    
        if limit:
            pipeline.append({"$limit": 3*limit})
            pipeline.append({"$sample": {"size": limit}})    
        return [item[K_ID] for item in self.beanstore.aggregate(pipeline=pipeline)]

    def sample_vector_search_tags(self, 
            embedding: list[float] = None, 
            min_score = None, 
            filter = None, 
            skip = 0,
            limit = 0
        ) -> list[Bean]:
        match = {K_TAGS: {"$exists": True}}
        if filter: match.update(filter)

        pipeline = [            
            {
                "$search": {
                    "cosmosSearch": {
                        "vector": embedding,
                        "path":   K_EMBEDDING,
                        "filter": match,
                        "k":      DEFAULT_VECTOR_SEARCH_LIMIT,
                    },
                    "returnStoredSource": True
                }
            },
            {
                "$addFields": { 
                    "search_score": {"$meta": "searchScore"} 
                }
            },
            {
                "$match": { 
                    "search_score": {"$gte": min_score or DEFAULT_VECTOR_SEARCH_SCORE} 
                }
            },
            { "$unwind": "$tags" },
            {
                "$group": {
                    K_ID: "$tags",
                    "count": { "$sum": 1 },
                }
            },
            { "$sort": {"count": -1} }
        ]
        if skip:
            pipeline.append({"$skip": skip})
        if limit:
            pipeline.append({"$limit": 3*limit})
            pipeline.append({"$sample": {"size": limit}})  
        return [item[K_ID] for item in self.beanstore.aggregate(pipeline=pipeline)]

    def get_cluster_sizes(self, urls: list[str]) -> list:
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
    
    def _query_beans_pipeline(self, filter, sort_by, skip, limit, projection, for_count):
        pipeline = []
        if filter:
            pipeline.append({"$match": filter})
        if sort_by:
            pipeline.append({"$sort": sort_by})        
        pipeline.append({"$group": CLUSTER_GROUP})
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

    def _text_search_pipeline(self, query: str, filter, sort_by, skip, limit, projection, for_count):
        match = {"$text": {"$search": query}}
        if filter: match.update(filter)

        pipeline = [
            { "$match": match },            
            { "$addFields":  { K_SEARCH_SCORE: {"$meta": "textScore"}} },
            { "$sort": {K_SEARCH_SCORE: -1} }
        ]        
        # means this is for retrieval of the actual contents
        # in this case sort by the what is provided for sorting
        pipeline.append({"$group": CLUSTER_GROUP})
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
   
    def _vector_search_pipeline(self, embedding, min_score, filter, sort_by, skip, limit, projection):    
        sort_by = sort_by or { "search_score": -1 }
        pipeline = [            
            {
                "$search": {
                    "cosmosSearch": {
                        "vector": embedding,
                        "path":   K_EMBEDDING,
                        "filter": filter or {},
                        "k":      DEFAULT_VECTOR_SEARCH_LIMIT, # if limit is 1, then we don't need to search for more than 1
                    }
                }
            },
            {
                "$addFields": { "search_score": {"$meta": "searchScore"} }
            },
            {
                "$match": { "search_score": {"$gte": min_score or DEFAULT_VECTOR_SEARCH_SCORE} }
            },
            {   
                "$sort": sort_by
            },
            {
                "$group": CLUSTER_GROUP
            },
            {   
                "$sort": sort_by
            },
        ]  
        if skip:
            pipeline.append({"$skip": skip})
        if limit:
            pipeline.append({"$limit": limit})
        if projection:
            pipeline.append({"$project": projection})
        return pipeline
    
    def _count_vector_search_pipeline(self, embedding, min_score, filter, limit):
        pipline = self._vector_search_pipeline(embedding, min_score, filter, None, 0, limit, None)
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
                    K_ID: {
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
    
    ##########################
    ## USER AND BARISTA OPS ##
    ##########################
    def get_user(self, email: str, linked_account: str = None) -> User|None:
        user = self.users.find_one({"email": email})
        if user:
            if linked_account and linked_account not in user["linked_accounts"]:
                self.link_account(email, linked_account)
            return User(**user)
        
    def create_user(self, userinfo: dict, following_baristas: list[str] = None):
        user = User(
            id=userinfo["email"], 
            email=userinfo["email"], 
            name=userinfo["name"], 
            image_url=userinfo.get("picture"), 
            created=datetime.now(),
            updated=datetime.now(),
            linked_accounts=[userinfo["iss"]],
            following=following_baristas
        )
        self.users.insert_one(user.model_dump(exclude_none=True, by_alias=True))
        return user

    def link_account(self, email: str, account: str):
        self.users.update_one(
            {"email": email}, 
            {
                "$addToSet": {"linked_accounts": account}
            }
        )

    def delete_user(self, email: str):
        self.users.delete_one({"_id": email})

    def follow_barista(self, email: str, barista_id: str):
        self.users.update_one(
            {"email": email}, 
            {
                "$addToSet": {"following": barista_id}
            }
        )
        return self.users.find_one({"email": email})["following"]

    def unfollow_barista(self, email: str, barista_id: str):
        self.users.update_one(
            {"email": email}, 
            {
                "$pull": {"following": barista_id}
            }
        )
        return self.users.find_one({"email": email})["following"]

    def get_barista(self, id: str) -> Barista:
        barista = self.baristas.find_one({K_ID: id})
        if barista: return Barista(**barista)

    def get_baristas(self, ids: list[str], projection: dict = None):
        filter = {K_ID: {"$in": ids}} if ids else {}
        return [Barista(**barista) for barista in self.baristas.find(filter, sort={K_TITLE: 1}, projection=projection)]
    
    def sample_baristas(self, limit: int, projection: dict = None):
        pipeline = [
            { "$match": {"public": True} },
            { "$sample": {"size": limit} }
        ]
        if projection: pipeline.append({ "$project": projection })

        return [Barista(**barista) for barista in self.baristas.aggregate(pipeline)]
     
    def get_following_baristas(self, user: User):
        following = self.users.find_one({K_ID: user.email}, {K_FOLLOWING: 1})
        if following: return list(following["following"])

    def search_baristas(self, query: str|list[str], projection: dict = None):
        pipeline = [
            {   
                "$match": {
                    "$text": {"$search": query if isinstance(query, str) else " ".join(query)},
                    "public": True
                } 
            },            
            {   "$addFields":  { "search_score": {"$meta": "textScore"}} },
            {   "$sort": {"search_score": -1} },
            {   "$limit": 10 }     
        ]    
        if projection: pipeline.append({ "$project": projection })
        return [Barista(**barista) for barista in self.baristas.aggregate(pipeline)]
    
    def publish(self, barista_id: str):
        return self.baristas.update_one(
            {K_ID: barista_id}, 
            { "$set": { "public": True } }
        ).acknowledged
        
    def unpublish(self, barista_id: str):
        return self.baristas.update_one(
            {K_ID: barista_id}, 
            { "$set": { "public": False } }
        ).acknowledged
        
    def is_published(self, barista_id: str):
        val = self.baristas.find_one({K_ID: barista_id}, {"public": 1, K_OWNER: 1})
        return val.get("public", val[K_OWNER] == SYSTEM) if val else False        

    def bookmark(self, user: User, url: str):
        return self.baristas.update_one(
            filter = {K_ID: user.email}, 
            update = { 
                "$addToSet": { "urls": url },
                "$setOnInsert": { 
                    K_OWNER: user.email,
                    K_TITLE: f"{user.name}'s Bookmarks",
                    K_DESCRIPTION: f"News, blogs and posts bookmarked by {user.name}"
                }
            },
            upsert = True
        ).acknowledged
    
    def unbookmark(self, user: User, url: str):
        return self.baristas.update_one(
            filter = {K_ID: user.email}, 
            update = { "$pull": { "urls": url } }
        ).acknowledged
    
    def is_bookmarked(self, user: User, url: str):
        return self.baristas.find_one({K_ID: user.email, "urls": url})
    

## local utilities for pymongo
def _deserialize_beans(cursor) -> list[Bean]:
    try:
        return [Bean(**item) for item in cursor]
    except:
        log.error("failed deserializing beans")
        return []

def _deserialize_chatters(cursor) -> list[Chatter]:
    try:
        return [Chatter(**item) for item in cursor]
    except:
        log.error("failed deserializing chatters")
        return []
    
def updated_after(last_ndays: int):
    return {K_UPDATED: {"$gte": ndays_ago(last_ndays)}}

def created_after(last_ndays: int):
    return {K_CREATED: {"$gte": ndays_ago(last_ndays)}}

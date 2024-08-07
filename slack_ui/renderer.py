from datetime import datetime
from itertools import chain
import queue
from shared import espressops, config, beanops, messages, llm, fields
from icecream import ic
import pandas as pd
import logging
from datetime import datetime as dt


UPDATE_INTEREST_VIEW={
    "type": "modal",
    "callback_id": "new_interest_input",
    "title": {"type": "plain_text", "text": "Espresso by Cafecit.io"},
    "submit": {"type": "plain_text", "text": "Update"},
    "blocks": [
        {
            "block_id": "new_interest_input",
            "type": "input",
            "element": {
                "type": "plain_text_input",
                "action_id": "new_interests"
            },
            "label": {
                "type": "plain_text",
                "text": "Your Interests (comma separated)"
            }
        }
    ]
}
DIVIDER = [{
    "type": "divider"
}]

logging.basicConfig(format="[%(asctime)s]: %(levelname)s - %(message)s",  datefmt='%d/%b/%Y %H:%M:%S')

_MAX_DISPLAY_BATCH_SIZE = 3

is_one_block = lambda data: data and isinstance(data, list) and isinstance(data[0], dict)
is_list_of_blocks = lambda data: data and isinstance(data, list) and isinstance(data[0], list)
is_text = lambda data: isinstance(data, str)

class ChannelManager:
    queues: dict[str, queue.Queue]
    clients: dict[str, any]

    def __init__(self):
        self.queues = {}

    def _get_channel(self, channel_id: str = None, channel_type: str = None, user_id: str = None, create_new = True) -> str:
        if channel_type == "directmessage":
            channel_id = user_id
        elif not channel_id:
            channel_id = user_id
        if create_new or (not self.queues.get(channel_id)):
            self.queues[channel_id] = queue.Queue()
        return channel_id
            
    # blocks can be: 
    #   - list[list[dict]]: represents an array of blocks where each set of blocks represents a news item
    #   - list[dict]: represents one news or display item
    #   - str: represents one text message
    def _queue_blocks(self, blocks, client, channel_id: str = None, channel_type: str = None, user_id: str = None):
        channel_id = self._get_channel(channel_id=channel_id, channel_type=channel_type, user_id=user_id, create_new=True)        
        if is_text(blocks) or is_one_block(blocks):
            # list[dict] or str --> represents 1 item
            self.queues[channel_id].put(blocks) 
        elif is_list_of_blocks(blocks):
            # list[list[dict]] --> represents a list of blocks, so merge them
            # add a divider after each block    
            blocks = [block+DIVIDER for block in blocks]     
            # merge each set of 3
            blocks = [list(chain(*blocks[i:i+_MAX_DISPLAY_BATCH_SIZE])) for i in range(0, len(blocks), _MAX_DISPLAY_BATCH_SIZE)]
            [self.queues[channel_id].put(item) for item in blocks]
        # don't do anything if the blocks are empty                    
   
    # returns a merge batch of blocks to display the batch to display        
    def _dequeue_blocks(self, channel_id: str) -> list[dict]|str:
        return self.queues[channel_id].get_nowait() if not self.queues[channel_id].empty() else None
    
    def next_page(self, client = None, channel_id: str = None, channel_type: str = None, user_id: str = None):
        channel_id = self._get_channel(channel_id=channel_id, channel_type=channel_type, user_id=user_id, create_new=False)
        page = self._dequeue_blocks(channel_id)

        if is_one_block(page):  
            # this is a set of blocks 
            client.chat_postMessage(channel=channel_id, text=f"Displaying items.", blocks=page)        
            remaining = self.queues[channel_id].qsize()        
            if remaining:
                client.chat_postMessage(channel=channel_id, text=f"Run */more* for more news and posts on this.")  
        elif is_text(page):
            client.chat_postMessage(channel=channel_id, text=page)                        
        else:
            client.chat_postMessage(channel=channel_id, text=messages.NO_MORE_CONTENT)

    def publish(self, blocks, client = None,  channel_id: str = None, channel_type: str = None, user_id: str = None):
        self._queue_blocks(blocks = blocks, client = client, channel_id=channel_id, channel_type=channel_type, user_id=user_id)
        self.next_page(client = client, channel_id=channel_id, channel_type=channel_type, user_id=user_id)


def get_user_home(username):
    pref_texts = espressops.get_preference_texts(config.SLACK, username)
    interests = _create_interests_blocks(username, pref_texts)
    user_nuggets = None
    if pref_texts:
        trending_for_user = beanops.trending_nuggets(espressops.get_preference_embeddings(source=config.SLACK, username=username), config.DEFAULT_WINDOW, config.DEFAULT_LIMIT)
        user_nuggets = _create_nugget_blocks(username, trending_for_user, config.DEFAULT_WINDOW, True, True) if trending_for_user else _create_text_blocks(messages.NOTHING_TRENDING)

    trending_globally = beanops.trending_nuggets(None, config.DEFAULT_WINDOW, config.DEFAULT_LIMIT)
    global_nuggets = _create_nugget_blocks(username, trending_globally, config.DEFAULT_WINDOW, True, False) if trending_globally else _create_text_blocks(messages.NOTHING_TRENDING)
    
    return _create_home_blocks(username, interests, user_nuggets, global_nuggets)

def get_trending_items(username: str, params: list[str]):
    # get the user preference and show the type of items the user wants
    prefs = espressops.get_preference_embeddings(source=config.SLACK, username=username)
    params = [p.strip().lower() for p in params if p.strip()]
    
    if (len(params) == 0) or ("nuggets" in params):
        # show everything that is trending regardless of interest/preference
        items = _create_nugget_blocks(username, 
            beanops.trending_nuggets(categories=prefs, window=config.DEFAULT_WINDOW, limit=10), 
            window=config.DEFAULT_WINDOW, for_home_page=False, preference_included=True)
        # items = _get_nuggets_blocks(user_id=username, categories=prefs, window=_DEFAULT_WINDOW, limit=10, for_home_page=False, preference_included=True)
    elif "news" in params:
        items = _create_bean_blocks(username, 
            beanops.trending_beans(categories=prefs, kinds=[config.ARTICLE], window=config.DEFAULT_WINDOW, limit=config.DEFAULT_LIMIT))
    elif "posts" in params:
        items = _create_bean_blocks(username, 
            beanops.trending_beans(categories=prefs, kinds=[config.POST], window=config.DEFAULT_WINDOW, limit=config.DEFAULT_LIMIT))
    else:
        items = messages.INVALID_INPUT

    return items or messages.NOTHING_TRENDING

def get_beans_by_category(username, category):
    embs = [item["embeddings"] for item in espressops.get_selected_preferences(source = config.SLACK, username=username, pref=category)]
    # if there is no embedding for this query with the text
    beans = beanops.trending_beans(categories=(embs or category), window=config.DEFAULT_WINDOW, limit=10)
    if not beans:
        return messages.NOTHING_TRENDING
    return [_create_text_blocks(f":label: *{category}*:")] + _create_bean_blocks(username, beans)

def get_beans_by_nugget(username, keyphrase: str, description: str, show_by_preference: bool, window: int):
    user_prefs = espressops.get_preference_embeddings(source=config.SLACK, username=username) if show_by_preference else None
    beans = beanops.search(nugget=keyphrase, categories=user_prefs, window=window, limit=10)    
    if not beans:
        # this should NOT return nothing, since it is already showing in the trending list
        logging.warning("get_beans(%s, %s, %d) came empty. Thats not supposed to happen", username, keyphrase, window)
        return messages.NOTHING_FOUND
    # always show the nuggets description as initial entry
    return [_create_text_blocks(f":rolled_up_newspaper: *{keyphrase}*: {description}")] + _create_bean_blocks(username, beans)

def get_beans_by_search(username, search_text: str):
    # this should search across the board without window
    beans = beanops.search(search_text=search_text, limit=10)
    return _create_bean_blocks(username, beans) if beans else messages.NOTHING_FOUND

def get_digests(username, search_text: str):
    # this should search across the board without window
    result = llm._create_digest(search_text, config.DEFAULT_WINDOW, config.DEFAULT_LIMIT)  
    return [_create_digest_blocks(nug, res, beans) for nug, res, beans in result] if result else messages.NOTHING_FOUND

def _create_digest_blocks(nugget, summary, beans): 
    # sources = {bean['source']: f"<{bean['url']}|{bean['source']}>" for bean in beans}
    return _create_text_blocks([
        f":rolled_up_newspaper: *{nugget[config.KEYPHRASE]}: {nugget[config.DESCRIPTION]}*", 
        summary,
        "*:link: * "+", ".join({bean['source']: f"<{bean['url']}|{bean['source']}>" for bean in beans}.values())
    ])

def _create_text_blocks(texts: str|list[str], accessory=None):
    if isinstance(texts, str):
        texts = [texts]
    
    result = []
    for t in texts:
        body = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": t,                
            }
        }
        if accessory:
            body["accessory"] = accessory
        result.append(body)
    return result

def _create_nugget_blocks(username, nuggets, window, for_home_page, preference_included): 
    if not nuggets:
        return None
    
    value = lambda data: f"{data.get('keyphrase')}//{data.get('description')}//{username}//{window}"    
    action_id = lambda data: "nugget//"+ data.get('keyphrase') + ("//show_by_preference" if preference_included else "")
    nugget_button = lambda data: {
        "type": "button",
        "text": {
            "type": "plain_text",
            "text": (":fire: " if data.get("match_count") >= config.FIRE_MIN else "") + data.get('keyphrase'),
            "emoji": True
        },
        "value": value(data),
        "action_id": action_id(data)
    }

    #  do a dedup, this is temporary breakfix
    nuggets = pd.DataFrame(nuggets).drop_duplicates(subset=['keyphrase']).to_dict('records')
    blocks = [
        {
            "type": "actions",
            "elements": [nugget_button(nugget) for nugget in nuggets]
        }
    ]    
    if not for_home_page:
        # if this is for chat window show these as texts and then show the buttons
        text_fields = lambda data: {
            "type": "mrkdwn",
            "text": f":white_small_square:*{data.get('keyphrase')}*: {data.get('event')}"
        }
        blocks = [
            {
                "type": "section",
                "fields": [text_fields(nugget) for nugget in nuggets]
            }
        ] + blocks

    return blocks

def _create_bean_banner(bean):
    get_url = lambda data: data.get('container_url') or data.get('url')
    get_source = lambda data: data.get('channel') or data.get('source')
    source_element = lambda data: {
        "type": "mrkdwn",
		"text": f":link: <{get_url(data)}|{get_source(data)}>"
    }

    date_element = lambda data: {
        "type": "plain_text",
        "text": f":date: {datetime.fromtimestamp(data.get('created') or data.get('updated')).strftime('%b %d, %Y')}"
    }

    author_element = lambda data: {
        "type": "plain_text",
		"text": f":writing_hand: {data.get('author')}" 
    }

    topic_element = lambda data: {
        "type": "plain_text",
		"text": f":label: {data.get('topic')}" 
    }
    
    comments_element = lambda data: {
        "type": "plain_text",
		"text": f":left_speech_bubble: {data.get('comments')}" 
    }

    likes_element = lambda data: {
        "type": "plain_text",
		"text": f":thumbsup: {data.get('likes')}" 
    }
    
    banner_elements = [source_element(bean), date_element(bean)]
    if 'topic' in bean:
        banner_elements.append(topic_element(bean))
    if 'comments' in bean:
        banner_elements.append(comments_element(bean))
    if 'likes' in bean:
        banner_elements.append(likes_element(bean))
    if 'author' in bean:
        banner_elements.append(author_element(bean))

    return {
        "type": "context",
        "elements": banner_elements
    }

def _create_bean_blocks(userid, beans):    
    body = lambda data: {        
		"type": "section",
		"text": {
			"type": "mrkdwn",
			"text": f"*{data.get('title').strip()}*\n{data.get('summary', '')}"
		}
    }    
    # action = lambda data: {    
	# 	"type": "actions",
	# 	"elements": [
	# 		{
    #             "action_id": f"positive",
    #             "type": "button",
	# 			"text": {
	# 				"type": "plain_text",
	# 				"text": ":ok_hand:",
    #                 "emoji": True
	# 			},
	# 			"value": data.get('url')
	# 		},
	# 		{
    #             "action_id": f"negative",
    #             "type": "button",
	# 			"text": {
	# 				"type": "plain_text",
	# 				"text": ":shit:",
    #                 "emoji": True
	# 			},
	# 			"value": data.get('url')
	# 		}
	# 	]
	# }    
    return [[_create_bean_banner(item), body(item)] for item in beans]

def _create_home_blocks(user_id, interests, trending_for_user, trending_globally):
    # THINGS TO SHOW
    # VIEW
    # [DONE] 1. Top 5 trending keywords/topics - 1 day, 1 week
    # 2. Social Media Stats - last 1 week
    # EDIT
    # [DONE] 1. Interests
    # [DONE] 2. Login to Reddit
    # 3. Login to LinkedIn 
    interests_header = [
        {
			"type": "header",
			"text": {
				"type": "plain_text",
				"text": "Your Interests"
			}
		}
    ] 
    trending_news_header = [
        {
			"type": "header",
			"text": {
				"type": "plain_text",
				"text": "Trending Today"
			}
		}
    ]
    user_trend_header = [
        {
			"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": "*For You*"
			}
		}
    ] 
    global_trend_header = [
        {
			"type": "section",
			"text": {
				"type": "mrkdwn",
				"text": "*Globally*"
			}
		}
    ]    
    blocks = interests_header + interests + DIVIDER + trending_news_header
    if trending_for_user:
        blocks += user_trend_header + trending_for_user
    return  blocks + global_trend_header + trending_globally

    # TODO: enable later
    # reddit part is working but it is not doing much
    # reddit_status = redditor.is_user_authenticated(user_id)
    # if reddit_status != True:
    #     reddit_element = {
	# 		"type": "actions",
	# 		"elements": [
	# 			{
	# 				"type": "button",
	# 				"text": {
	# 					"type": "plain_text",
	# 					"text": "Reddit"
	# 				},
	# 				"value": "reddit",
	# 				"url": reddit_status,
	# 				"action_id": "connect:reddit"
	# 			}
	# 		]
	# 	}
    # else:
    #     reddit_element = {
	# 		"type": "section",
	# 		"text": {
	# 			"type": "mrkdwn",
	# 			"text": "*Reddit* : Connected :large_green_circle: (Your soul now belongs to us)"
	# 		}
	# 	}

    # connect = [
    #     {
	# 		"type": "header",
	# 		"text": {
	# 			"type": "plain_text",
	# 			"text": "Connect Your Accounts"
	# 		}
	# 	},
    #     reddit_element,
    #     {
	# 		"type": "actions",
	# 		"elements": [
	# 			{
	# 				"type": "button",
	# 				"text": {
	# 					"type": "plain_text",
	# 					"text": "LinkedIn",
	# 					"emoji": True
	# 				},
	# 				"value": "linkedin",
	# 				"url": "http://www.linkedin.com",
	# 				"action_id": "connect:linkedin"
	# 			}
	# 		]
	# 	}
    # ]
    
def _create_interests_blocks(user_id, interests):
    interest_button = lambda data: {
		"type": "button",
		"text": {
			"type": "plain_text",
			"text": data
		},
		"value": f"{data}//{user_id}",
		"action_id": f"category//{data})"
	}
    update_button = {
        "type": "button",
        "text": {
            "type": "plain_text",
            "text": "Update",
            "emoji": False
        },
        "style": "primary",
        "value": user_id,
        "action_id": f"update_interests:{user_id}"
    }
    if interests:
        return [
            {
                "type": "actions",
                "elements": [interest_button(item) for item in interests] + [update_button]
            }
        ]
    else:
        return _create_text_blocks(messages.NO_INTERESTS_MESSAGE, update_button)

def update_user_preferences(user_id: str, interests: list[str]):
    espressops.update_topics(source=config.SLACK, username=user_id, items=interests)    
 
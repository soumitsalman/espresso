import logging
import os
import time
from fastapi import HTTPException, Query
from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request
from starlette.responses import RedirectResponse
from nicegui import app, ui
from fastapi.responses import FileResponse, Response
from icecream import ic
import env
from pybeansack.datamodels import *
from shared import config

##### LOGGING SETUP SECTION #####

logging.basicConfig(level=logging.WARNING, format='%(asctime)s|%(name)s|%(levelname)s|%(message)s', datefmt='%Y-%m-%d %H:%M:%S')
app_logger: logging.Logger = config.create_logger("__APP__", '%(asctime)s|%(name)s|%(levelname)s|%(message)s|%(user_id)s|%(page_id)s|%(q)s|%(acc)s|%(tag)s|%(kind)s|%(ndays)s', "espresso-app.log")
api_logger: logging.Logger = config.create_logger("__API__", '%(asctime)s|%(name)s|%(levelname)s|%(message)s|%(user_id)s|%(q)s|%(acc)s|%(url)s|%(tag)s|%(kind)s|%(source)s|%(ndays)s|%(start)s|%(limit)s|%(num_items)s', "espresso-api.log")

def log_app(function, **kwargs): 
    user = logged_in_user()
    extra = {"user_id": user[espressops.ID] if user else None, "page_id": None, "q": None, "acc": None, "url": None, "tag": None, "kind": None, "ndays": None}
    extra.update(kwargs)
    app_logger.info(function, extra=extra)

def log_api(function, **kwargs):    
    extra = {"user_id": None, "q": None, "acc": None, "url": None, "tag": None, "kind": None, "source": None, "ndays": None, "start": None, "limit": None, "num_items": None}
    extra.update(kwargs)
    api_logger.info(function, extra=extra)

##### SLACK APP SECTION #####
from slack_bolt.adapter.fastapi import SlackRequestHandler
from slack_ui.handler import slack_app

handler = SlackRequestHandler(slack_app)

@app.post("/slack/events")
@app.post("/slack/commands")
@app.post("/slack/actions")
@app.get("/slack/oauth-redirect")
@app.get("/slack/install")
async def receive_slack_app_events(req: Request):
    res = await handler.handle(req)
    return res


##### WEB APP SECTION #####
from pybeansack.embedding import *
from shared import beanops, config, espressops, messages
import web_ui.pages
import web_ui.renderer

oauth = OAuth()

def session_settings() -> dict:
    if 'settings' not in app.storage.user:
        app.storage.user['settings'] = config.default_user_settings()
    return app.storage.user['settings']

def last_page() -> str:
    return session_settings().get('last_page', "/")

def temp_user():
    return app.storage.user.get("temp_user")

def set_temp_user(user):
    app.storage.user["temp_user"] = user

def clear_temp_user():
    if 'temp_user' in app.storage.user:
        del app.storage.user["temp_user"]

def logged_in_user():
    return app.storage.user.get('logged_in_user')

def set_logged_in_user(registered_user):
    app.storage.user['logged_in_user'] = registered_user  
    settings = session_settings() 
    if espressops.PREFERENCES in registered_user:        
        settings['search']['last_ndays'] = registered_user[espressops.PREFERENCES]['last_ndays']
    settings['search']['topics'] = espressops.get_user_category_ids(registered_user) or settings['search']['topics']

def log_out_user():
    if 'logged_in_user' in app.storage.user:
        del app.storage.user['logged_in_user']

@app.get("/web/slack/login")
async def slack_login(request: Request):
    redirect_uri = os.getenv('HOST_URL')+"/web/slack/oauth-redirect"
    return await oauth.slack.authorize_redirect(request, redirect_uri)

@app.get("/web/slack/oauth-redirect")
async def slack_web_redirect(request: Request):
    try:
        token = await oauth.slack.authorize_access_token(request)
        user = (await oauth.slack.get('https://slack.com/api/users.identity', token=token)).json()    
        return _redirect_after_auth(user['user']['name'], user['user']['id'], user['user'].get('image_72'), config.SLACK, token)
    except Exception as err:
        logging.warning(err)
        return RedirectResponse("/login-failed?source=slack")

@app.get("/reddit/login")
async def reddit_login(request: Request):
    redirect_uri = os.getenv('HOST_URL')+"/reddit/oauth-redirect"
    return await oauth.reddit.authorize_redirect(request, redirect_uri)

@app.get("/reddit/oauth-redirect")
async def reddit_redirect(request: Request):    
    try:
        token = await oauth.reddit.authorize_access_token(request)
        user = (await oauth.reddit.get('https://oauth.reddit.com/api/v1/me', token=token)).json()
        return _redirect_after_auth(user['name'], user['id'], user.get('icon_img'), config.REDDIT, token)
    except Exception as err:
        logging.warning(err)
        return RedirectResponse("/login-failed?source=reddit")

def _redirect_after_auth(name, id, image_url, source, token):
    authenticated_user = {
        espressops.NAME: name,
        espressops.SOURCE_ID: id,
        espressops.SOURCE: source,
        espressops.IMAGE_URL: image_url,
        **token
    }
    # if a user is already logged in then add this as a connection
    current_user = logged_in_user()
    if current_user:
        espressops.add_connection(current_user, authenticated_user)
        current_user[espressops.CONNECTIONS][source]=name
        log_app('connection added')
        return RedirectResponse(last_page())
        
    # if no user is logged in but there is an registered user with this cred then log-in that user    
    registered_user = espressops.get_user(authenticated_user)
    if registered_user:
        set_logged_in_user(registered_user)
        log_app('logged in')
        return RedirectResponse(last_page()) 

    set_temp_user(authenticated_user)
    return RedirectResponse("/user-registration")

@app.get('/logout')
def logout():
    log_app('logged out')
    log_out_user()
    return RedirectResponse(last_page())

@app.get("/images/{name}")
async def image(name: str):
    path = "./images/"+name
    if os.path.exists(path):
        return FileResponse(path, media_type="image/png")
    return Response(content=messages.RESOURCE_NOT_FOUND, status_code=404)

@ui.page('/login-failed')
async def login_failed(source: str):
    web_ui.pages.render_login_failed(f'/{source}/login', last_page())

@ui.page('/user-registration')
def user_registration():
    log_app('user_registration', user_id=temp_user()[espressops.ID] if temp_user() else None)
    web_ui.pages.render_user_registration(
        session_settings(), 
        temp_user(),
        lambda user: [set_logged_in_user(user), clear_temp_user(), ui.navigate.to(last_page())],
        lambda: [clear_temp_user(), ui.navigate.to(last_page())])

@ui.page("/")
def home():  
    settings = session_settings()
    settings['last_page'] = "/" 
    log_app('home')
    web_ui.pages.render_home(settings, logged_in_user())

@ui.page("/search")
def search(
    q: str = None, 
    acc: float = Query(ge=0, le=1, default=config.DEFAULT_ACCURACY),
    tag: list[str] | None = Query(max_length=config.MAX_LIMIT, default=None),
    kind: list[str] | None = Query(max_length=config.MAX_LIMIT, default=None),
    ndays: int | None = Query(ge=config.MIN_WINDOW, le=config.MAX_WINDOW, default=None)):

    settings = session_settings()
    settings['last_page'] = web_ui.renderer.make_navigation_target("/search", q=q, tag=tag, kind=kind, ndays=ndays, acc=acc)
    log_app('search', q=q, tag=tag, kind=kind, ndays=ndays, acc=acc)
    web_ui.pages.render_search(settings, logged_in_user(), q, acc, tag, kind, ndays)

@ui.page("/page/{category}")
def trending(
    category: str, 
    ndays: int | None = Query(ge=config.MIN_WINDOW, le=config.MAX_WINDOW, default=config.DEFAULT_WINDOW)):    
    if not web_ui.pages.category_exists(category):
        return Response(content=messages.RESOURCE_NOT_FOUND, status_code=404)
    
    settings = session_settings()
    settings['last_page'] = web_ui.renderer.make_navigation_target(f"/page/{category}", ndays=ndays) 
    log_app('page', page_id=category, ndays=ndays)
    web_ui.pages.render_trending(settings, logged_in_user(), category.lower(), ndays)

@ui.page("/channel/{userid}")
def user_channel(
    userid: str, 
    ndays: int | None = Query(ge=config.MIN_WINDOW, le=config.MAX_WINDOW, default=config.DEFAULT_WINDOW)):
    if not web_ui.pages.channel_exists(userid):
        return Response(content=messages.RESOURCE_NOT_FOUND, status_code=404)
    
    settings = session_settings()
    settings['last_page'] = web_ui.renderer.make_navigation_target(f"/channel/{userid}", ndays=ndays) 
    log_app('channel', page_id=userid, ndays=ndays)
    web_ui.pages.render_user_channel(settings, logged_in_user(), userid, ndays)

@ui.page("/docs/{doc}")
async def document(doc: str):
    path = f"./documents/{doc}.md"
    if not os.path.exists(path):
        return Response(content=messages.RESOURCE_NOT_FOUND, status_code=404)
    
    log_app('docs', page_id=doc)
    web_ui.pages.render_document(session_settings(), logged_in_user(), path)      


##### API SECTION #####
@app.get("/api/beans", response_model=list[Bean])
async def get_beans(
    url: list[str] | None = Query(max_length=config.MAX_LIMIT, default=None),
    tag: list[str] | None = Query(max_length=config.MAX_LIMIT, default=None),
    kind: list[str] | None = Query(max_length=config.MAX_LIMIT, default=None), 
    source: list[str] = Query(max_length=config.MAX_LIMIT, default=None),
    ndays: int | None = Query(ge=config.MIN_WINDOW, le=config.MAX_WINDOW, default=None), 
    start: int | None = Query(ge=0, default=0), 
    limit: int | None = Query(ge=config.MIN_LIMIT, le=config.MAX_LIMIT, default=config.MAX_LIMIT)):
    """
    Retrieves the bean(s) with the given URL(s).
    """
    res = beanops.get(url, tag, kind, source, ndays, start, limit)  
    log_api('get_beans', url=url, tag=tag, kind=kind, source=source, ndays=ndays, start=start, limit=limit, num_items=len(res) if res else None)
    # return respond(res, "No beans found")
    return res

@app.get("/api/beans/search", response_model=list[Bean])
async def search_beans(
    q: str = None, 
    acc: float = Query(ge=0, le=1, default=config.DEFAULT_ACCURACY),
    tag: list[str] | None = Query(max_length=config.MAX_LIMIT, default=None),
    kind: list[str] | None = Query(max_length=config.MAX_LIMIT, default=None), 
    source: list[str] = Query(max_length=config.MAX_LIMIT, default=None),
    ndays: int | None = Query(ge=config.MIN_WINDOW, le=config.MAX_WINDOW, default=None), 
    start: int | None = Query(ge=0, default=0), 
    limit: int | None = Query(ge=config.MIN_LIMIT, le=config.MAX_LIMIT, default=config.DEFAULT_LIMIT)):
    """
    Search beans by various parameters.
    q: query string
    acc: accuracy
    tags: list of tags
    kinds: list of kinds
    source: list of sources
    ndays: last n days
    start: start index
    limit: limit
    """
    res = beanops.search(q, acc, tag, kind, source, ndays, start, limit)
    log_api('search_beans', q=q, acc=acc, tag=tag, kind=kind, source=source, ndays=ndays, start=start, limit=limit, num_items=len(res) if res else None)
    # return respond(res, "No beans found")
    return res
@app.get("/api/beans/unique", response_model=list[Bean])
async def unique_beans(
    tag: list[str] | None = Query(max_length=config.MAX_LIMIT, default=None),
    kind: list[str] | None = Query(default=None), 
    source: list[str] = Query(max_length=config.MAX_LIMIT, default=None),
    ndays: int | None = Query(ge=config.MIN_WINDOW, le=config.MAX_WINDOW, default=None), 
    start: int | None = Query(ge=0, default=0), 
    limit: int | None = Query(ge=config.MIN_LIMIT, le=config.MAX_LIMIT, default=config.MAX_LIMIT)):
    """
    Retuns a set of unique beans, meaning only one bean from each cluster will be included in the result.
    To retrieve all the beans irrespective of cluster, use /beans endpoint.
    To retrieve the beans related to the beans in this result set, use /beans/related endpoint.
    """
    res = beanops.unique(tag, kind, source, ndays, start, limit)
    log_api('unique_beans', tag=tag, kind=kind, source=source, ndays=ndays, start=start, limit=limit, num_items=len(res) if res else None)
    # return respond(res, "No beans found")
    return res

@app.get("/api/beans/related", response_model=list[Bean]|None)
async def get_related_beans(
    url: str, 
    tag: list[str] | None = Query(max_length=config.MAX_LIMIT, default=None),
    kind: list[str] | None = Query(default=None), 
    source: list[str] = Query(max_length=config.MAX_LIMIT, default=None),
    ndays: int | None = Query(ge=config.MIN_WINDOW, le=config.MAX_WINDOW, default=None), 
    start: int | None = Query(ge=0, default=0), 
    limit: int | None = Query(ge=config.MIN_LIMIT, le=config.MAX_LIMIT, default=config.MAX_LIMIT)):
    """
    Retrieves the related beans to the given bean.
    """    
    res = beanops.related(url, tag, kind, source, ndays, start, limit)
    log_api('get_related_beans', url=url, tag=tag, kind=kind, source=source, ndays=ndays, start=start, limit=limit, num_items=len(res) if res else None)
    # return respond(res, "No beans found")
    return res

@app.get("/api/beans/chatters", response_model=list[Chatter])
async def get_chatters(url: list[str] | None = Query(max_length=config.MAX_LIMIT, default=None)):
    """
    Retrieves the latest social media stats for the given bean(s).
    """
    res = beanops.chatters(url)
    log_api('get_chatters', url=url, num_items=len(res) if res else None)
    # return respond(res, "No chatters found")
    return res

@app.get("/api/beans/sources")
async def get_sources():
    """
    Retrieves the list of sources.
    """
    res = beanops.sources()
    log_api('get_sources', num_items=len(res) if res else None)
    # return respond(res, "No sources found")  
    return res

def initialize_server():
    embedder = RemoteEmbeddings(env.llm_base_url(), env.llm_api_key(), env.embedder_model(), env.embedder_n_ctx()) \
        if env.llm_base_url() else \
        BeansackEmbeddings(env.embedder_model(), env.embedder_n_ctx())
    beanops.initiatize(env.db_connection_str(), embedder)
    espressops.initialize(env.db_connection_str(), env.sb_connection_str(), embedder)

    oauth.register(
        name=config.REDDIT,
        client_id=config.reddit_client_id(),
        client_secret=config.reddit_client_secret(),
        user_agent=config.APP_NAME,
        authorize_url='https://www.reddit.com/api/v1/authorize',
        access_token_url='https://www.reddit.com/api/v1/access_token', 
        api_base_url="https://oauth.reddit.com/",
        client_kwargs={'scope': 'identity mysubreddits'}
    )
    oauth.register(
        name=config.SLACK,
        client_id=config.slack_client_id(),
        client_secret=config.slack_client_secret(),
        user_agent=config.APP_NAME,
        authorize_url='https://slack.com/oauth/authorize',
        access_token_url='https://slack.com/api/oauth.access',
        client_kwargs={'scope': 'identity.basic,identity.avatar'},
    )

initialize_server()
ui.run(title=config.APP_NAME, favicon="images/favicon.jpg", storage_secret=os.getenv('INTERNAL_AUTH_TOKEN'), host="0.0.0.0", port=8080, show=False, binding_refresh_interval=0.3, dark=True)

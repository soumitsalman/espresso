import os
import logging
from icecream import ic
from app.pybeansack.models import *
from app.shared.env import *
from app.shared.consts import *
from app.web import beanops, vanilla
from app.web.context import *

import jwt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, Path, Query
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, FileResponse, PlainTextResponse
from authlib.integrations.starlette_client import OAuth
from nicegui import ui, app
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_ipaddr

REGISTRATION_INFO_KEY = "registration_info"

JWT_TOKEN_KEY = 'espressotoken'
JWT_TOKEN_LIFETIME = timedelta(days=30) # TODO: change this later to 30 days
JWT_TOKEN_REFRESH_WINDOW = timedelta(hours=1) # TODO: change this later to 5 minutes

LIMIT_5_A_MINUTE = "5/minute"
LIMIT_10_A_MINUTE = "10/minute"

Q = Query(
    ..., 
    min_length=3, 
    max_length=512,
    description="The search query string. Minimum length is 3 characters."
)
URL = Query(
    ..., 
    min_length=10, 
    description="The URL of the bean for which related beans are to be found. Minimum length is 10 characters."
)
ACCURACY = Query(
    default=config.filters.page.default_accuracy, 
    ge=0, le=1,
    description="Minimum cosine similarity score (only applicable to vector search)."
)
TAGS = Query(
    max_length=MAX_LIMIT, 
    default=None, 
    description="One or more tags such as entities, categories or regions to filter beans."
)
SOURCES = Query(
    max_length=MAX_LIMIT, 
    default=None, 
    description="One or more source ids to filter beans."
)
WINDOW = Query(ge=beanops.MIN_WINDOW, le=beanops.MAX_WINDOW, default=config.filters.page.default_window)

logger: logging.Logger = logging.getLogger(config.app.name)
logger.setLevel(logging.INFO)

jwt_token_exp = lambda: datetime.now() + JWT_TOKEN_LIFETIME
jwt_token_needs_refresh = lambda data: (datetime.now() - JWT_TOKEN_REFRESH_WINDOW).timestamp() < data['exp']
get_unauthenticated_user = lambda request: app.storage.browser.get("id") or get_ipaddr(request)

oauth = OAuth()
limiter = Limiter(key_func=get_unauthenticated_user, swallow_errors=True)

def create_jwt_token(email: str):
    data = {
        "email": email,
        "iat": datetime.now(),
        "exp": jwt_token_exp()
    }
    return jwt.encode(data, config.app.storage_secret, algorithm="HS256")

def decode_jwt_token(token: str):
    try:
        data = jwt.decode(token, config.app.storage_secret, algorithms=["HS256"], verify=True)
        return data if (data and "email" in data) else None
    except Exception as err:
        log("jwt_token_decode_error", user_id=app.storage.browser.get("id"), error=str(err))
        return None

@app.on_startup
def initialize_server():    
    # if hasattr(config.oauth, 'google'):
    oauth.register(
            "google",
            client_id=os.getenv('GOOGLE_CLIENT_ID'),
            client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),        
            server_metadata_url=GOOGLE_SERVER_METADATA_URL,
            authorize_url=GOOGLE_AUTHORIZE_URL,
            access_token_url=GOOGLE_ACCESS_TOKEN_URL,
            api_base_url=GOOGLE_API_BASE_URL,
            userinfo_endpoint=GOOGLE_USERINFO_ENDPOINT,
            client_kwargs=GOOGLE_OAUTH_SCOPE,
            user_agent=config.app.name
        )    
    # if hasattr(config.oauth, 'slack'):
    oauth.register(
        "slack",
        client_id=os.getenv('SLACK_CLIENT_ID'),
            client_secret=os.getenv('SLACK_CLIENT_SECRET'),  
        server_metadata_url=SLACK_SERVER_METADATA_URL,
        authorize_url=SLACK_AUTHORIZE_URL,
        access_token_url=SLACK_ACCESS_TOKEN_URL,
        api_base_url=SLACK_API_BASE_URL,
        client_kwargs=SLACK_OAUTH_SCOPE,
        user_agent=config.app.name
    )
    # if hasattr(config.oauth, 'linkedin'):
    oauth.register(
        "linkedin",
        client_id=os.getenv('LINKEDIN_CLIENT_ID'),
            client_secret=os.getenv('LINKEDIN_CLIENT_SECRET'),  
        authorize_url=LINKEDIN_AUTHORIZE_URL,
        access_token_url=LINKEDIN_ACCESS_TOKEN_URL,
        api_base_url=LINKEDIN_API_BASE_URL,
        client_kwargs=LINKEDIN_OAUTH_SCOPE,
        user_agent=config.app.name
    )
    # if hasattr(config.oauth, 'reddit'):
    oauth.register(
        name="reddit",
        client_id=os.getenv('REDDIT_CLIENT_ID'),
        client_secret=os.getenv('REDDIT_CLIENT_SECRET'),  
        authorize_url=REDDIT_AUTHORIZE_URL,
        access_token_url=REDDIT_ACCESS_TOKEN_URL, 
        api_base_url=REDDIT_API_BASE_URL,
        client_kwargs=REDDIT_OAUTH_SCOPE,
        user_agent=config.app.name
    )    
    
    logger.info("server_initialized")

def validate_page(page_id: str) -> Page:
    page_id = page_id.lower()
    stored_page = beanops.db.get_page(page_id)
    if not stored_page: raise HTTPException(status_code=404, detail=f"{page_id} not found")
    return stored_page

def validate_bean_url(url: str) -> Page:
    bean = db.get_bean(url, project={K_URL: 1, K_TITLE: 1, K_ENTITIES: 1, K_CATEGORIES: 1, K_REGIONS: 1})
    if not bean: raise HTTPException(status_code=404, detail=f"{url} not found")
    return bean

def validate_doc(doc_id: str):
    if not bool(os.path.exists(f"docs/{doc_id}")):
        raise HTTPException(status_code=404, detail=f"{doc_id} not found")
    return f"./docs/{doc_id}"

def validate_image(image_id: str):
    if not bool(os.path.exists(f"images/{image_id}")):
        raise HTTPException(status_code=404, detail=f"{image_id} not found")
    return f"./images/{image_id}"

def validate_registration():
    userinfo = app.storage.browser.get(REGISTRATION_INFO_KEY)
    if not userinfo:
        raise HTTPException(status_code=401, detail="Unauthorized")
    del app.storage.browser[REGISTRATION_INFO_KEY]
    return userinfo

def validate_authenticated_user():
    token = app.storage.browser.get(JWT_TOKEN_KEY)
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    data = decode_jwt_token(token)
    if not data:
        del app.storage.browser[JWT_TOKEN_KEY]
        raise HTTPException(status_code=401, detail="Unauthorized")
    user = beanops.db.get_user(data["email"])
    if not user:
        del app.storage.browser[JWT_TOKEN_KEY]
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user

def create_context(page_id: str|Page|Bean, request: Request, page_type: str = None) -> Context:
    try:
        user = validate_authenticated_user()
    except:
        user = get_unauthenticated_user(request)
    return Context(page_id, user, page_type)

def login_user(user: dict|User):
    email = user.email if isinstance(user, User) else user['email']
    app.storage.browser[JWT_TOKEN_KEY] = create_jwt_token(email)
    log("login_user", user_id=email)

def process_oauth_result(result: dict):
    existing_user = beanops.db.get_user(result['userinfo']['email'], result['userinfo']['iss'])
    if existing_user:
        login_user(existing_user)        
        return RedirectResponse("/")
    else:
        login_user(result['userinfo'])
        app.storage.browser[REGISTRATION_INFO_KEY] = result['userinfo']
        return RedirectResponse("/user/register")

@app.get("/oauth/google/login")
async def google_oauth_login(request: Request):
    log("oauth_login", user_id=get_unauthenticated_user(request), provider="google")
    return await oauth.google.authorize_redirect(request, os.getenv('BASE_URL') + "/oauth/google/redirect")

@app.get("/oauth/google/redirect")
async def google_oauth_redirect(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
        return process_oauth_result(token)
    except Exception as err:
        log("oauth_error", user_id=get_ipaddr(request), provider="google", error=str(err))
        return RedirectResponse("/")

@app.get("/oauth/slack/login")
async def slack_oauth_login(request: Request):
    log("oauth_login", user_id=get_unauthenticated_user(request), provider="slack")
    return await oauth.slack.authorize_redirect(request, os.getenv('BASE_URL') + "/oauth/slack/redirect")

@app.get("/oauth/slack/redirect")
async def slack_oauth_redirect(request: Request):
    try:
        token = await oauth.slack.authorize_access_token(request)
        return process_oauth_result(token)  
    except Exception as err:
        log("oauth_error", user_id=get_unauthenticated_user(request), provider="slack", error=str(err))
        return RedirectResponse("/")
    
@app.get("/oauth/linkedin/login")
async def linkedin_oauth_login(request: Request):
    log("oauth_login", user_id=get_unauthenticated_user(request), provider="linkedin")
    return await oauth.linkedin.authorize_redirect(request, os.getenv('BASE_URL') + "/oauth/linkedin/redirect")

@app.get("/oauth/linkedin/redirect")
async def linkedin_oauth_redirect(request: Request):
    try:
        token = await oauth.linkedin.authorize_access_token(request)
        return process_oauth_result(token) 
    except Exception as err:
        log("oauth_error", user_id=get_unauthenticated_user(request), provider="linkedin", error=str(err))
        return RedirectResponse("/")

@app.get("/user/me/logout")
async def logout_user(user: beanops.User|str = Depends(validate_authenticated_user)):
    log("logout_user", user_id=user)
    if JWT_TOKEN_KEY in app.storage.browser:
        del app.storage.browser[JWT_TOKEN_KEY]
    return RedirectResponse("/")

@app.get("/user/me/delete")
async def delete_user(user: beanops.User|str = Depends(validate_authenticated_user)):
    log("delete_user", user_id=user)
    beanops.db.delete_user(user.email)
    if JWT_TOKEN_KEY in app.storage.browser:
        del app.storage.browser[JWT_TOKEN_KEY]
    return RedirectResponse("/")

@app.get("/docs/{doc_id}")
async def document(request: Request,
    doc_id: str = Depends(validate_doc, use_cache=True)
):
    context = create_context(doc_id, request)
    context.log('read doc')
    return FileResponse(doc_id, media_type="text/markdown")
    
@app.get("/images/{image_id}")
async def image(image_id: str = Depends(validate_image, use_cache=True)):    
    return FileResponse(image_id, media_type="image/png")

@ui.page("/", title="Espresso")
@limiter.limit(LIMIT_5_A_MINUTE, error_message=LIMIT_ERROR_MSG)
async def home(request: Request):
    context = create_context("home", request)  
    await vanilla.render_home(context)

@ui.page("/sources/{source_id}", title="Espresso News, Posts and Blogs")
@limiter.limit(LIMIT_10_A_MINUTE, error_message=LIMIT_ERROR_MSG)
async def custom_source_page(
    request: Request, 
    source_id: str = Path(),
    tags: list[str] = TAGS
):
    context = create_context(source_id, request, K_SOURCE)
    context.sources = [source_id]
    context.tags = tags
    await vanilla.render_custom_page(context)

@ui.page("/categories/{category}", title="Espresso News, Posts and Blogs")
@limiter.limit(LIMIT_10_A_MINUTE, error_message=LIMIT_ERROR_MSG)
async def custom_category_page(
    request: Request, 
    category: str = Path(),
    tags: list[str] = TAGS,
    sources: list[str] = SOURCES
):
    context = create_context(category, request, K_CATEGORIES)
    context.tags = [tags, [category]] if tags else [category]
    context.sources = sources
    await vanilla.render_custom_page(context)

@ui.page("/entities/{entity}", title="Espresso News, Posts and Blogs")
@limiter.limit(LIMIT_10_A_MINUTE, error_message=LIMIT_ERROR_MSG)
async def custom_entity_page(
    request: Request, 
    entity: str = Path(),
    tags: list[str] = TAGS,
    sources: list[str] = SOURCES
):
    context = create_context(entity, request, K_ENTITIES)
    context.tags = [tags, [entity]] if tags else [entity]
    context.sources = sources
    await vanilla.render_custom_page(context)

@ui.page("/regions/{region}", title="Espresso News, Posts and Blogs")
@limiter.limit(LIMIT_10_A_MINUTE, error_message=LIMIT_ERROR_MSG)
async def custom_region_page(
    request: Request, 
    region: str = Path(),
    tags: list[str] = TAGS,
    sources: list[str] = SOURCES
):
    context = create_context(region, request, K_REGIONS)
    context.tags = [tags, [region]] if tags else [region]
    context.sources = sources
    await vanilla.render_custom_page(context)

@ui.page("/related", title="Espresso News, Posts and Blogs")
@limiter.limit(LIMIT_10_A_MINUTE, error_message=LIMIT_ERROR_MSG)
async def related(
    request: Request, 
    url: str = URL,
    tags: list[str] = TAGS,
    sources: list[str] = SOURCES
):
    bean = validate_bean_url(url)
    context = create_context(bean, request, K_RELATED)
    context.tags = tags
    context.sources = sources
    await vanilla.render_related_beans_page(context)

@ui.page("/search", title="Espresso Search")
@limiter.limit(LIMIT_5_A_MINUTE, error_message=LIMIT_ERROR_MSG)
async def search(request: Request, 
    q: str = Q,
    acc: float = ACCURACY,
    tags: list[str] = TAGS,
    sources: list[str] = SOURCES,
    ndays: int = WINDOW,
):
    context = create_context("search", request)
    context.query = q
    context.accuracy = acc
    context.last_ndays = ndays
    context.tags = tags
    context.sources = sources
    await vanilla.render_search(context)

@ui.page("/pages/{page_id}", title="Espresso")
@limiter.limit(LIMIT_5_A_MINUTE, error_message=LIMIT_ERROR_MSG)
async def stored_page(request: Request, page_id: Page = Depends(validate_page, use_cache=True)): 
    context = create_context(page_id, request)
    if not context.has_read_permission:
        raise HTTPException(status_code=401, detail="Unauthorized")
    await vanilla.render_stored_page(context)

@ui.page("/user/register", title="Espresso User Registration")
@limiter.limit(LIMIT_5_A_MINUTE, error_message=LIMIT_ERROR_MSG)
async def register_user(request: Request, userinfo: dict = Depends(validate_registration)):
    context = Context("registration", userinfo)
    await vanilla.render_registration(context)
    

def run():
    app.add_middleware(SessionMiddleware, secret_key=os.getenv('APP_STORAGE_SECRET')) # needed for oauth
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    ui.run(
        title=config.app.name, 
        storage_secret=os.getenv('APP_STORAGE_SECRET'),
        dark=True, 
        favicon="./images/favicon.ico", 
        port=8080, 
        show=False,
        uvicorn_reload_includes="*.py,*/web/styles.css,*.toml",
        proxy_headers=True
    )
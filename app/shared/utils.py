from datetime import datetime, timedelta
import humanize
from urllib.parse import urlparse
import logging
from icecream import ic
from app.pybeansack.models import Barista, User
from app.shared.env import *

# cache settings
HALF_HOUR = 1800
ONE_HOUR = 3600
FOUR_HOURS = 14400
ONE_DAY = 86400
ONE_WEEK = 604800
CACHE_SIZE = 100

logger = logging.getLogger(APP_NAME)

# this is the user navigation and access context that also arbitrates RBAC
# TODO: move this to a different file
class NavigationContext:
    user: User|str|None = None
    page: Barista|str = None
    
    # filter_tags: list[str]|None = None
    kind: str|None = None
    sort_by: str|None = None

    query: str|None = None
    tags: list[str]|None = None
    sources: list[str]|None = None
    accuracy: float|None = None
    last_ndays: int|None = None

    def __init__(self, page: Barista|str, user: User|str):
        self.page = page
        self.user = user
        
    @property
    def user_id(self):
        if isinstance(self.user, User): return self.user.email
        if isinstance(self.user, str): return self.user
        if isinstance(self.user, dict): return self.user["email"]

    @property
    def page_id(self):
        if isinstance(self.page, Barista): return self.page.id
        if isinstance(self.page, str): return self.page

    @property
    def is_registered(self):
        return isinstance(self.user, User)
    
    @property
    def is_barista(self):
        return isinstance(self.page, Barista)

    @property
    def has_read_permission(self):
        # anyone has access to public baristas
        # if the barista is marked as private, then only the owner can access it
        # which means if this is not a registered user, then user does not have access to the barista
        if not self.is_barista: return True
        if self.page.public: return True
        return (self.user.email == self.page.owner) if (self.is_registered) else False

    @property
    def has_publish_permission(self):
        # only barista pages can be published
        # only registered user that owns the barista can publish
        if not self.is_registered: return False
        if not self.is_barista: return False
        return self.user.email == self.page.owner

    @property
    def has_follow_permission(self):
        # anyone can follow public baristas
        # if the barista is marked as private, then only the owner can follow it
        if not self.is_registered: return False
        if not self.is_barista: return False
        if self.page.public: return True
        return self.user.email == self.page.owner
    
    @property
    def is_following(self):
        if not self.is_registered: return False
        if not self.is_barista: return False
        return self.page.id in self.user.following

    def log(self, action, **kwargs):    
        extra = {
            "user_id": self.user_id,
            "page_id": self.page_id,
            "tags": str(self.tags) if self.tags else None,
            "kinds": str(self.kind) if self.kind else None,
            "sort_by": self.sort_by,
            "query": self.query,
            "sources": str(self.sources) if self.sources else None,
            "accuracy": self.accuracy,
            "ndays": self.last_ndays
        }
        if kwargs:
            extra.update(kwargs)
        log(action, **extra)

def log(function, **kwargs):   
    # transform the values before logging for flat tables
    kwargs = {key: (str(value) if isinstance(value, list) else value) for key, value in kwargs.items() if value}
    logger.info(function, extra=kwargs)

is_valid_url = lambda url: urlparse(url).scheme in ["http", "https"]
favicon = lambda bean: "https://www.google.com/s2/favicons?domain="+urlparse(bean.url).netloc
naturalday = lambda date_val: humanize.naturalday(date_val, format="%a, %b %d")
ndays_ago = lambda ndays: datetime.now() - timedelta(days=ndays)
now = datetime.now

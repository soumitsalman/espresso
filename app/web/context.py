import logging
from icecream import ic
from app.pybeansack.models import Bean, Page, User
from app.shared.env import *

# this is the user navigation and access context that also arbitrates RBAC
# TODO: move this to a different file
class Context:
    user: User|str|None = None
    page: Page|str|Bean = None
    page_type: str = None
    kind: str|None = None
    sort_by: str|None = None
    query: str|None = None
    tags: list[str]|None = None
    sources: list[str]|None = None
    topic: str = None
    accuracy: float|None = None
    last_ndays: int|None = None

    def __init__(self, page: Page|str|Bean, user: User|str, page_type: str = None):
        self.page = page
        self.user = user
        self.page_type = "stored_page" if isinstance(page, Page) else page_type
        
    @property
    def user_id(self):
        if isinstance(self.user, User): return self.user.email
        if isinstance(self.user, str): return self.user
        if isinstance(self.user, dict): return self.user["email"]

    @property
    def page_id(self):
        if isinstance(self.page, Page): return self.page.id
        if isinstance(self.page, str): return self.page
        if isinstance(self.page, Bean): return self.page.url

    @property
    def is_user_registered(self):
        return isinstance(self.user, User)
    
    @property
    def is_stored_page(self):
        return isinstance(self.page, Page)

    @property
    def has_read_permission(self):
        # anyone has access to public baristas
        # if the barista is marked as private, then only the owner can access it
        # which means if this is not a registered user, then user does not have access to the barista
        if not self.is_stored_page: return True
        if self.page.public: return True
        return (self.user.email == self.page.owner) if (self.is_user_registered) else False

    @property
    def has_publish_permission(self):
        # only barista pages can be published
        # only registered user that owns the barista can publish
        if not self.is_user_registered: return False
        if not self.is_stored_page: return False
        return self.user.email == self.page.owner

    @property
    def has_follow_permission(self):
        # anyone can follow public baristas
        # if the barista is marked as private, then only the owner can follow it
        if not self.is_user_registered: return False
        if not self.is_stored_page: return False
        if self.page.public: return True
        return self.user.email == self.page.owner
    
    @property
    def is_following(self):
        if not self.is_user_registered: return False
        if not self.is_stored_page: return False
        return self.page.id in self.user.following

    def log(self, action, **kwargs):    
        extra = {
            "user_id": self.user_id,
            "page_id": self.page_id,
            "page_type": f"custom_page:{self.page_type}" if self.is_stored_page else "saved_page",
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
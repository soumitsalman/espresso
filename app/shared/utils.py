from datetime import datetime, timedelta
import humanize
from urllib.parse import urlparse
import logging
from app.pybeansack.models import User
from app.shared.env import *

# cache settings
ONE_HOUR = 3600
FOUR_HOURS = 14400
ONE_DAY = 86400
ONE_WEEK = 604800
CACHE_SIZE = 100

logger = logging.getLogger(APP_NAME)

def log(function, **kwargs):    
    # transform the values before logging for flat tables
    if "user_id" in kwargs:
        kwargs["user_id"] = user_id(kwargs["user_id"])
    kwargs = {key: (str(value) if isinstance(value, list) else value) for key, value in kwargs.items() if value}
    logger.info(function, extra=kwargs)

def user_id(user):
    if isinstance(user, User): return user.email
    if isinstance(user, str): return user

is_valid_url = lambda url: urlparse(url).scheme in ["http", "https"]
favicon = lambda bean: "https://www.google.com/s2/favicons?domain="+urlparse(bean.url).netloc
naturalday = lambda date_val: humanize.naturalday(date_val, format="%a, %b %d")
ndays_ago = lambda ndays: datetime.now() - timedelta(days=ndays)
now = datetime.now

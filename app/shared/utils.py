import re
import humanize 
from datetime import datetime, timedelta
from urllib.parse import urlparse

is_valid_url = lambda url: urlparse(url).scheme in ["http", "https"]

favicon = lambda bean: "https://www.google.com/s2/favicons?domain="+urlparse(bean.url).netloc
naturalday = lambda date_val: humanize.naturalday(date_val, format="%a, %b %d")
ndays_ago = lambda ndays: datetime.now() - timedelta(days=ndays)
now = datetime.now

field_value = lambda items: {"$in": items} if isinstance(items, list) else items
lower_case = lambda items: {"$in": [item.lower() for item in items]} if isinstance(items, list) else items.lower()
case_insensitive = lambda items: {"$in": [re.compile(item, re.IGNORECASE) for item in items]} if isinstance(items, list) else re.compile(items, re.IGNORECASE)

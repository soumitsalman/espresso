import re
import humanize 
from datetime import datetime, timedelta
from urllib.parse import urlparse

is_valid_url = lambda url: urlparse(url).scheme in ["http", "https"]
favicon = lambda bean: "https://www.google.com/s2/favicons?domain="+bean.site_base_url
naturalday = lambda date_val: humanize.naturalday(date_val, format="%a, %b %d")
naturalnum = humanize.intword
# ndays_ago = lambda ndays: datetime.now() - timedelta(days=ndays)
# now = datetime.now

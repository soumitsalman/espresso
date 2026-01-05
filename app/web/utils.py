import logging
import humanize 
from datetime import datetime, timedelta
from urllib.parse import urlparse

def read_file(path: str) -> str:
    with open(path, "r") as file: 
        return file.read()

to_list = lambda x: x if isinstance(x, list) else [x]
is_valid_url = lambda url: urlparse(url).scheme in ["http", "https"]
site_name = lambda bean: bean.publisher.title if bean.publisher and bean.publisher.title else bean.source
favicon = lambda bean: bean.publisher.favicon if bean.publisher and bean.publisher.favicon else f"https://www.google.com/s2/favicons?domain={bean.source}"
naturalday = lambda date_val: humanize.naturalday(date_val, format="%a, %b %d")
naturalnum = humanize.intword


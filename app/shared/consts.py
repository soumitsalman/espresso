FAVICON_URL="https://cafecito-assets.sfo3.cdn.digitaloceanspaces.com/espresso-favicon.ico"

### Time Values ###
HALF_HOUR = 1800
ONE_HOUR = 3600
FOUR_HOURS = 14400
ONE_DAY = 86400
ONE_WEEK = 604800

### Query limits ###
MIN_WINDOW = 1
MAX_WINDOW = 30
MIN_LIMIT = 1
MAX_LIMIT = 100

### Oauth related constants ###
GOOGLE_SERVER_METADATA_URL = 'https://accounts.google.com/.well-known/openid-configuration'
GOOGLE_AUTHORIZE_URL = 'https://accounts.google.com/o/oauth2/auth'
GOOGLE_ACCESS_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_API_BASE_URL = 'https://www.googleapis.com/oauth2/v1/'
GOOGLE_USERINFO_ENDPOINT = 'https://openidconnect.googleapis.com/v1/userinfo'
GOOGLE_OAUTH_SCOPE = {'scope': 'openid email profile'}

SLACK_SERVER_METADATA_URL = 'https://slack.com/.well-known/openid-configuration'
SLACK_AUTHORIZE_URL = 'https://slack.com/openid/connect/authorize'
SLACK_ACCESS_TOKEN_URL = 'https://slack.com/api/openid.connect.token'
SLACK_API_BASE_URL = 'https://slack.com/api'
SLACK_OAUTH_SCOPE = {'scope': 'openid profile email'}

LINKEDIN_AUTHORIZE_URL = 'https://www.linkedin.com/oauth/v2/authorization'
LINKEDIN_ACCESS_TOKEN_URL = 'https://www.linkedin.com/oauth/v2/accessToken'
LINKEDIN_API_BASE_URL = 'https://api.linkedin.com/v2'
LINKEDIN_OAUTH_SCOPE = {'scope': 'openid profile email'}

REDDIT_AUTHORIZE_URL = 'https://www.reddit.com/api/v1/authorize'
REDDIT_ACCESS_TOKEN_URL = 'https://www.reddit.com/api/v1/access_token'
REDDIT_API_BASE_URL = 'https://oauth.reddit.com'
REDDIT_OAUTH_SCOPE = {'scope': 'identity mysubreddits'}

### User Messages ###
NO_INTERESTS_MESSAGE = "Is there anything under god's green earth that you find interesting? Just do some clickittyclack and tell us what floats your boat."
NO_MORE_BEANS = "Thass'it ... Se acabo! Go get some :coffee:"
MORE_BEANS = "More stories in the queue. Type 'more' for loading the next page."
NOT_IMPLEMENTED = "I don't really do much. I just sit here and look pretty."
LOGIN_FIRST = "Imma' need you to Login first"
NOTHING_TRENDING = "Nothing trending."

NOTHING_FOUND = "That's all she wrote 🤷🏽!"
RESOURCE_NOT_FOUND = "Never heard of 'em"
# NOTHING_TRENDING = "Nothing trending."
# NOTHING_TRENDING_IN = "Nothing trending in last %d day(s)."
# UNKNOWN = "💩 ... I don't know what this is."
UNKNOWN_INPUT = "Yeah ... so, I don't know what this is. I'm just going to go ahead search for: %s"
UNKNOWN_ERROR = "💩 ... try again?!"

PROCESSING = "🏃⛏️💩..."
PUBLISHED = "👍 Published"

IN_MAINTENANCE = "Taking an EPIC 💩! We will be back soon... (famous last words, yes we know)"

HOME_BANNER_TEXT = "News, Stories, Blogs and more"
# CONSOLE_EXAMPLES = ["trending -q automotive-logistics", "search -q \"Earnings reports\" -t Apple", "publish url1 url2 url3"]   
CONSOLE_PLACEHOLDER = "Tell me lies, sweet little lies"
SEARCH_BEANS_PLACEHOLDER = "What would you like to know today?"
SEARCH_BARISTA_PLACEHOLDER = "Find your filtered pour"

COOKIE_NOTIFICATION = "We use cookies which are necessary for maintaining your browsing session experience on our website. By continuing to use this site, you agree to our use of cookies."
LIMIT_ERROR_MSG = "Slow down cuh, it ain't that kinda party"
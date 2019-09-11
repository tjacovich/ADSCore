LOGGING_LEVEL = "INFO"
LOG_STDOUT = True
ADS_URL = "https://prod.adsabs.harvard.edu/"
API_URL = ADS_URL+"v1/"
ENVIRONMENT = "localhost"
SERVER_BASE_URL = "/"
BOOTSTRAP_SERVICE = API_URL+"accounts/bootstrap"
SEARCH_SERVICE = API_URL+"search/query"
EXPORT_SERVICE = API_URL+"export/bibtex"
VAULT_SERVICE = API_URL+"vault/query"
OBJECTS_SERVICE =  API_URL+"objects/query"
RESOLVER_SERVICE =  API_URL+"resolver/"
GRAPHICS_SERVICE =  API_URL+"graphics/"
METRICS_SERVICE =  API_URL+"metrics"
LINKGATEWAY_SERVICE =  ADS_URL+"link_gateway/"
API_TIMEOUT = 90
SECRET_KEY = "mjnahGS3CmaVsSfSVGxxytGTGa2vX1CPPoT7gZvIpIQiOZREJwsvfNzWooQx1BA1"
SESSION_COOKIE_NAME = "session-core"
SESSION_COOKIE_PATH = SERVER_BASE_URL
CACHE_TYPE = "simple" # redis
CACHE_DEFAULT_TIMEOUT = 300 # seconds (expire in N seconds)
CACHE_THRESHOLD = 100 # only for SimpleCache and FileSystemCache
CACHE_IGNORE_ERRORS = True # only for SimpleCache and FileSystemCache
CACHE_KEY_PREFIX = "CACHE/core"
CACHE_MANUAL_KEY_PREFIX = "/DATA" # In addition to CACHE_KEY_PREFIX for manually storing in the cache
CACHE_REDIS_URL = "redis://redis-backend:6379"
RATELIMIT_DEFAULT = None # individual per route
RATELIMIT_APPLICATION = "400 per day" # shared by all routes; same value as in https://github.com/adsabs/adsws/blob/9ec9087d2baa4bbf754a8fb5cf915fa1032725ae/adsws/accounts/views.py#L853
RATELIMIT_STORAGE_URL = "memory://" # "redis://redis-backend:6379"
RATELIMIT_STRATEGY = "fixed-window"
RATELIMIT_HEADERS_ENABLED = True
RATELIMIT_ENABLED = True
RATELIMIT_SWALLOW_ERRORS = True
RATELIMIT_KEY_PREFIX = "core" # The final prefix will be LIMITER/core


SORT_OPTIONS = [
    { 'id': 'author_count', 'text': 'Authors', 'description': 'sort by number of authors' },
    { 'id': 'bibcode', 'text': 'Bibcode', 'description': 'sort by bibcode' },
    { 'id': 'citation_count', 'text': 'Citations', 'description': 'sort by number of citations' },
    { 'id': 'citation_count_norm', 'text': 'Norm. Citations', 'description': 'sort by number of normalized citations' },
    { 'id': 'classic_factor', 'text': 'Classic Factor', 'description': 'sort using classical score' },
    { 'id': 'first_author', 'text': 'First Author', 'description': 'sort by first author' },
    { 'id': 'date', 'text': 'Date', 'description': 'sort by publication date' },
    { 'id': 'entry_date', 'text': 'Entry Date', 'description': 'sort by date work entered the database' },
    { 'id': 'read_count', 'text': 'Reads', 'description': 'sort by number of reads' },
    { 'id': 'score', 'text': 'Score', 'description': 'sort by the relative score' }
]

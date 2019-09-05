LOGGING_LEVEL = "INFO"
LOG_STDOUT = True
ADS_URL = "https://dev.adsabs.harvard.edu/"
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
API_TIMEOUT = 90
SECRET_KEY = "mjnahGS3CmaVsSfSVGxxytGTGa2vX1CPPoT7gZvIpIQiOZREJwsvfNzWooQx1BA1"
SESSION_COOKIE_NAME = "session-core"
SESSION_COOKIE_PATH = SERVER_BASE_URL

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

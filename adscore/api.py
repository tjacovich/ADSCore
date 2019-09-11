import json
import datetime
import functools
import urllib.parse
from collections.abc import Mapping
from flask import session, current_app
from requests.exceptions import ConnectionError, ConnectTimeout, ReadTimeout

def bootstrap():
    """
    Get an anonymous token, if the user already has a session, the same token
    will be recovered from the API unless it has expired (in which case, a new
    renewed one will be received)
    """
    params = None
    auth = _request(current_app.config['BOOTSTRAP_SERVICE'], params, method="GET", retry_counter=0)
    return { 'access_token': auth['access_token'], 'expire_in': auth['expire_in'] }

def store_query(bibcodes, sort="date desc, bibcode desc"):
    """
    Store query in vault
    """
    data = {
                'bigquery': ["bibcode\n"+"\n".join(bibcodes)],
                'fq': ["{!bitset}"],
                'q': ["*:*"],
                'sort': [sort]
            }
    return _request(current_app.config['VAULT_SERVICE'], data, method="POST", retry_counter=0)

def objects_query(object_names, retry_counter=0):
    """
    Transform object into ID
    """
    data = {
                'query': ["object:({})".format(",".join(object_names))],
            }
    return _request(current_app.config['OBJECTS_SERVICE'], data, method="POST", retry_counter=0)

def link_gateway(identifier, section, retry_counter=0):
    """
    Retrieve associated works
    """
    params = None
    return _request(current_app.config['LINKGATEWAY_SERVICE'] + identifier + "/" + section, params, method="GET", retry_counter=0)

class Search(Mapping):
    def __init__(self, q, rows=25, start=0, sort="date desc", fields="title,bibcode,author,citation_count,pubdate,[citations],property,esources,data"):
        try:
            cache = list(current_app.extensions['cache'].keys())[0]
            storage = cache.get("/".join((current_app.config['CACHE_MANUAL_KEY_PREFIX'], q, str(rows), str(start), sort, fields)))
        except Exception:
            # Do not affect users if connection to Redis is lost in production
            if current_app.debug:
                raise
            storage = None
            cache = None
        if storage:
            self._storage = storage
        else:
            self._storage = {}
            if "bibcode desc" not in sort:
                # Add secondary sort criteria
                sort += ", bibcode desc"
            # Add statistics if citation counts is the sorting criteria
            if "citation_count_norm" in sort:
                stats = 'true'
                stats_field = 'citation_count_norm'
            elif "citation_count" in sort:
                stats = 'true'
                stats_field = 'citation_count'
            else:
                stats = 'false'
                stats_field = ''
            params = {
                        'fl': fields,
                        'q': q,
                        'rows': rows,
                        'sort': sort,
                        'start': start,
                        'stats': stats,
                        'stats.field': stats_field
                        }
            results = _search(params)
            self._storage.update(self._process(results))
            try:
                if cache:
                    cache.set("/".join((current_app.config['CACHE_MANUAL_KEY_PREFIX'], q, str(rows), str(start), sort, fields)), self._storage)
            except Exception:
                # Do not affect users if connection to Redis is lost in production
                if current_app.debug:
                    raise

    def __getitem__(self, key):
        return self._storage[key]

    def __iter__(self):
        return iter(self._storage)

    def __len__(self):
        return len(self._storage)

    def _process_data(self, data):
        # Data is reported as LABEL:NUMBER, split and sort by number in decreasing mode
        data_list = []
        for data_element in data:
            data_components = data_element.split(":")
            if len(data_components) >= 2:
                try:
                    data_list.append((data_components[0], int(data_components[1])))
                except ValueError:
                    data_list.append((data_components[0], 0))
            else:
                data_list.append((data_components[0], 0))
        sorted_data_list = sorted(data_list, key=functools.cmp_to_key(lambda x, y: 1 if x[1] < y[1] else -1))
        return sorted_data_list

    def _process(self, results):
        """
        Sanitize data
        """
        if 'error' in results:
            return results
        else:
            for i in range(len(results['response']['docs'])):
                results['response']['docs'][i]['reference_count'] = results['response']['docs'][i]['[citations]']['num_references']
                if 'data' in results['response']['docs'][i]:
                    results['response']['docs'][i]['data'] = self._process_data(results['response']['docs'][i]['data'])

                # Ensure title is a list
                if 'title' in results['response']['docs'][i] and not isinstance(results['response']['docs'][i]['title'], list):
                    results['response']['docs'][i]['title'] = [results['response']['docs'][i]['title']]

                # Extract page from list
                if 'page' in results['response']['docs'][i] and isinstance(results['response']['docs'][i]['page'], list) and len(results['response']['docs'][i]['page']) > 0:
                    results['response']['docs'][i]['page'] = results['response']['docs'][i]['page'][0]

                # Parse publication date and store it as Month Year (e.g., September 2019)
                if 'pubdate' in results['response']['docs'][i]:
                    try:
                        results['response']['docs'][i]['formatted_pubdate'] = datetime.datetime.strptime(results['response']['docs'][i]['pubdate'], '%Y-%m-00').strftime("%B %Y")
                    except ValueError:
                        pass

                # Find arXiv ID
                if 'identifier' in results['response']['docs'][i]:
                    results['response']['docs'][i]['arXiv'] = None
                    for element in results['response']['docs'][i]['identifier']:
                        if element.startswith("arXiv:"):
                            results['response']['docs'][i]['arXiv'] = element
                            break
            return results

class Abstract(Mapping):
    def __init__(self, identifier):
        try:
            cache = list(current_app.extensions['cache'].keys())[0]
            storage = cache.get(identifier)
        except Exception:
            # Do not affect users if connection to Redis is lost in production
            if current_app.debug:
                raise
            storage = None
            cache = None
        if storage:
            self._storage = storage
        else:
            self._storage = {}
            docs = _abstract(identifier)
            if docs and len(docs) > 0:
                self._storage.update(self._augment(docs[0]))
            else:
                self._storage['error'] = "Record not found."
            try:
                if cache:
                    cache.set(identifier, self._storage)
            except Exception:
                # Do not affect users if connection to Redis is lost in production
                if current_app.debug:
                    raise

    def __getitem__(self, key):
        return self._storage[key]

    def __iter__(self):
        return iter(self._storage)

    def __len__(self):
        return len(self._storage)

    def _augment(self, doc):
        """
        Retreive complementary data
        """
        # Retrieve extra information
        associated = _resolver(doc['bibcode'], resource="associated")
        if 'error' not in associated:
            doc['associated'] = associated.get('links', {}).get('records', [])
        else:
            doc['associated'] = []

        graphics = _graphics(doc['bibcode'])
        if 'error' not in graphics:
            doc['graphics'] = graphics
        else:
            doc['graphics'] = []

        metrics = _metrics(doc['bibcode'])
        if 'error' not in metrics and 'Error' not in metrics:
            doc['metrics'] = metrics
        else:
            doc['metrics'] = {}

        export = _export(doc['bibcode'])
        if 'error' not in export:
            doc['export'] = export.get('export')
        else:
            doc['export'] = None

        return doc


def _request(endpoint, params, method="GET", retry_counter=0):
    """
    Execute query
    """
    if session.get('auth', {}).get('access_token'):
        headers = { "Authorization": "Bearer:{}".format(session['auth']['access_token']), }
    else:
        headers = None

    if method == "GET":
        if params:
            url = endpoint + "?" + urllib.parse.urlencode(params)
        else:
            url = endpoint
        data = None
    else: # POST
        url = endpoint
        data = params
    try:
        r = getattr(current_app.client, method.lower())(url, json=data, headers=headers, cookies=session['cookies'], timeout=current_app.config['API_TIMEOUT'], verify=False)
    except (ConnectionError, ConnectTimeout, ReadTimeout) as e:
        msg = str(e)
        return {"error": "{}".format(msg)}
    if not r.ok:
        if r.status_code == 401 and retry_counter == 0: # Unauthorized
            # Re-try only once bootstrapping a new token
            session['auth'] = bootstrap()
            return _request(endpoint, params, method=method, retry_counter=retry_counter+1)
        try:
            msg = r.json().get('error', {})
            if type(msg) is dict:
                msg = msg.get('msg', msg)
        except:
            msg = r.content
        return {"error": "{} (HTTP status code {})".format(msg, r.status_code)}
    #r.raise_for_status()
    r.cookies.clear_expired_cookies()
    session['cookies'].update(r.cookies.get_dict())
    try:
        results = r.json()
    except json.decoder.JSONDecodeError:
        results = {"error": "Response is not JSON compatible: {}".format(r.content)}
    return results

def _abstract(identifier):
    """
    Retrieve abstract
    """
    q = 'identifier:{0}'.format(identifier)
    fields = 'identifier,[citations],abstract,author,bibcode,citation_count,comment,issn,isbn,doi,id,keyword,page,property,esources,pub,pub_raw,pubdate,pubnote,read_count,title,volume,data'
    search = Search(q, rows=1, start=0, sort="date desc", fields=fields)
    return search.get('response', {}).get('docs', [])

def _export(bibcode, retry_counter=0):
    """
    Export bibtex
    """
    data = {
            'bibcode': ['{0}'.format(bibcode)],
            'sort': 'date desc, bibcode desc',
            }
    return _request(current_app.config['EXPORT_SERVICE'], data, method="POST", retry_counter=0)

def _search(params):
    return _request(current_app.config['SEARCH_SERVICE'], params, method="GET", retry_counter=0)

def _resolver(identifier, resource="associated", retry_counter=0):
    """
    Retrieve associated works
    """
    params = None
    return _request(current_app.config['RESOLVER_SERVICE'] + identifier + "/" + resource, params, method="GET", retry_counter=0)

def _graphics(identifier, retry_counter=0):
    """
    Retrieve associated works
    """
    params = None
    return _request(current_app.config['GRAPHICS_SERVICE'] + identifier, params, method="GET", retry_counter=0)

def _metrics(bibcode):
    """
    Metrics
    """
    data = {
            'bibcodes': ['{0}'.format(bibcode)],
            }
    return _request(current_app.config['METRICS_SERVICE'], data, method="POST", retry_counter=0)


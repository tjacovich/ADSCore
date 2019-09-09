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
    r = current_app.client.get(current_app.config['BOOTSTRAP_SERVICE'], cookies=session['cookies'], timeout=current_app.config['API_TIMEOUT'], verify=False)
    r.raise_for_status()
    r.cookies.clear_expired_cookies()
    session['cookies'].update(r.cookies.get_dict())
    auth = r.json()
    return { 'access_token': auth['access_token'], 'expire_in': auth['expire_in'] }

def _abstract(identifier, retry_counter=0):
    """
    Retrieve abstract
    """
    headers = { "Authorization": "Bearer:{}".format(session['auth']['access_token']), }
    params = urllib.parse.urlencode({
            'fl': 'identifier,[citations],abstract,aff,author,bibcode,citation_count,comment,issn,isbn,doi,id,keyword,page,property,esources,pub,pub_raw,pubdate,pubnote,read_count,title,volume,data',
            'q': 'identifier:{0}'.format(identifier),
            'rows': '25',
            'sort': 'date desc, bibcode desc',
            'start': '0'
            })
    try:
        r = current_app.client.get(current_app.config['SEARCH_SERVICE'] + "?" + params, headers=headers, cookies=session['cookies'], timeout=current_app.config['API_TIMEOUT'], verify=False)
    except (ConnectionError, ConnectTimeout, ReadTimeout) as e:
        msg = str(e)
        return {"error": "{}".format(msg)}
    if not r.ok:
        if r.status_code == 401 and retry_counter == 0: # Unauthorized
            # Re-try only once bootstrapping a new token
            session['auth'] = bootstrap()
            return _abstract(identifier, retry_counter=retry_counter+1)
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
    else:
        for i in range(len(results['response']['docs'])):
            results['response']['docs'][i]['reference_count'] = results['response']['docs'][i]['[citations]']['num_references']
    return results

def _export(bibcode, retry_counter=0):
    """
    Export bibtex
    """
    headers = { "Authorization": "Bearer:{}".format(session['auth']['access_token']), }
    data = {
            'bibcode': ['{0}'.format(bibcode)],
            'sort': 'date desc, bibcode desc',
            }
    try:
        r = current_app.client.post(current_app.config['EXPORT_SERVICE'], json=data, headers=headers, cookies=session['cookies'], timeout=current_app.config['API_TIMEOUT'], verify=False)
    except (ConnectionError, ConnectTimeout, ReadTimeout) as e:
        msg = str(e)
        return {"error": "{}".format(msg)}
    if not r.ok:
        if r.status_code == 401 and retry_counter == 0: # Unauthorized
            # Re-try only once bootstrapping a new token
            session['auth'] = bootstrap()
            return _export(bibcode, retry_counter=retry_counter+1)
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

def store_query(bibcodes, sort="date desc, bibcode desc"):
    """
    Store query in vault
    """
    headers = { "Authorization": "Bearer:{}".format(session['auth']['access_token']), }
    data = {
                'bigquery': ["bibcode\n"+"\n".join(bibcodes)],
                'fq': ["{!bitset}"],
                'q': ["*:*"],
                'sort': [sort]
            }
    r = current_app.client.post(current_app.config['VAULT_SERVICE'], json=data, headers=headers, cookies=session['cookies'], timeout=current_app.config['API_TIMEOUT'], verify=False)
    r.raise_for_status()
    r.cookies.clear_expired_cookies()
    session['cookies'].update(r.cookies.get_dict())
    try:
        results = r.json()
    except json.decoder.JSONDecodeError:
        results = {"error": "Response is not JSON compatible: {}".format(r.content)}
    return results

def objects_query(object_names, retry_counter=0):
    """
    Transform object into ID
    """
    headers = { "Authorization": "Bearer:{}".format(session['auth']['access_token']) }
    data = {
                'query': ["object:({})".format(",".join(object_names))],
            }
    try:
        r = current_app.client.post(current_app.config[OBJECTS_SERVICE], json=data, headers=headers, cookies=session['cookies'], timeout=current_app.config['API_TIMEOUT'], verify=False)
    except (ConnectionError, ConnectTimeout, ReadTimeout) as e:
        msg = str(e)
        return {"error": "{}".format(msg)}
    if not r.ok:
        if r.status_code == 401 and retry_counter == 0: # Unauthorized
            # Re-try only once bootstrapping a new token
            session['auth'] = bootstrap()
            return objects_query(object_names, retry_counter=retry_counter+1)
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

def search(q, rows=25, start=0, sort="date desc", retry_counter=0):
    """
    Execute query
    """
    headers = { "Authorization": "Bearer:{}".format(session['auth']['access_token']), }
    if "bibcode desc" not in sort:
        # Add secondary sort criteria
        sort += ", bibcode desc"
    if "citation_count_norm" in sort:
        stats = 'true'
        stats_field = 'citation_count_norm'
    elif "citation_count" in sort:
        stats = 'true'
        stats_field = 'citation_count'
    else:
        stats = 'false'
        stats_field = ''
    params = urllib.parse.urlencode({
                    'fl': 'title,bibcode,author,citation_count,pubdate,[citations],property,esources,data',
                    'q': '{0}'.format(q),
                    'rows': '{0}'.format(rows),
                    'sort': '{0}'.format(sort),
                    'start': '{0}'.format(start),
                    'stats': stats,
                    'stats.field': stats_field
                })
    try:
        r = current_app.client.get(current_app.config['SEARCH_SERVICE'] + "?" + params, headers=headers, cookies=session['cookies'], timeout=current_app.config['API_TIMEOUT'], verify=False)
    except (ConnectionError, ConnectTimeout, ReadTimeout) as e:
        msg = str(e)
        return {"error": "{}".format(msg)}
    if not r.ok:
        if r.status_code == 401 and retry_counter == 0: # Unauthorized
            # Re-try only once bootstrapping a new token
            session['auth'] = bootstrap()
            return search(q, rows=rows, start=start, sort=sort, retry_counter=retry_counter+1)
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
    else:
        for i in range(len(results['response']['docs'])):
            results['response']['docs'][i]['reference_count'] = results['response']['docs'][i]['[citations]']['num_references']
            if results['response']['docs'][i].get('data'):
                data = []
                for data_element in results['response']['docs'][i]['data']:
                    data_components = data_element.split(":")
                    if len(data_components) >= 2:
                        try:
                            data.append((data_components[0], int(data_components[1])))
                        except ValueError:
                            data.append((data_components[0], 0))
                    else:
                        data.append((data_components[0], 0))
                data = sorted(data, key=functools.cmp_to_key(lambda x, y: 1 if x[1] < y[1] else -1))
                results['response']['docs'][i]['data'] = data
    return results

def _resolver(identifier, resource="associated", retry_counter=0):
    """
    Retrieve associated works
    """
    headers = { "Authorization": "Bearer:{}".format(session['auth']['access_token']), }
    try:
        r = current_app.client.get(current_app.config['RESOLVER_SERVICE'] + identifier + "/" + resource, headers=headers, cookies=session['cookies'], timeout=current_app.config['API_TIMEOUT'], verify=False)
    except (ConnectionError, ConnectTimeout, ReadTimeout) as e:
        msg = str(e)
        return {"error": "{}".format(msg)}
    if not r.ok:
        if r.status_code == 401 and retry_counter == 0: # Unauthorized
            # Re-try only once bootstrapping a new token
            session['auth'] = bootstrap()
            return _resolver(identifier, retry_counter=retry_counter+1)
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

def _graphics(identifier, retry_counter=0):
    """
    Retrieve associated works
    """
    headers = { "Authorization": "Bearer:{}".format(session['auth']['access_token']), }
    try:
        r = current_app.client.get(current_app.config['GRAPHICS_SERVICE'] + identifier, headers=headers, cookies=session['cookies'], timeout=current_app.config['API_TIMEOUT'], verify=False)
    except (ConnectionError, ConnectTimeout, ReadTimeout) as e:
        msg = str(e)
        return {"error": "{}".format(msg)}
    if not r.ok:
        if r.status_code == 401 and retry_counter == 0: # Unauthorized
            # Re-try only once bootstrapping a new token
            session['auth'] = bootstrap()
            return _graphics(identifier, retry_counter=retry_counter+1)
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

def _metrics(bibcode):
    """
    Metrics
    """
    headers = { "Authorization": "Bearer:{}".format(session['auth']['access_token']), }
    data = {
            'bibcodes': ['{0}'.format(bibcode)],
            }
    try:
        r = current_app.client.post(current_app.config['METRICS_SERVICE'], json=data, headers=headers, cookies=session['cookies'], timeout=current_app.config['API_TIMEOUT'], verify=False)
    except (ConnectionError, ConnectTimeout, ReadTimeout) as e:
        msg = str(e)
        return {"error": "{}".format(msg)}
    if not r.ok:
        if r.status_code == 401 and retry_counter == 0: # Unauthorized
            # Re-try only once bootstrapping a new token
            session['auth'] = bootstrap()
            return _metrics(bibcode, retry_counter=retry_counter+1)
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

def link_gateway(identifier, section, retry_counter=0):
    """
    Retrieve associated works
    """
    headers = { "Authorization": "Bearer:{}".format(session['auth']['access_token']), }
    try:
        r = current_app.client.get(current_app.config['LINKGATEWAY_SERVICE'] + identifier + "/" + section, headers=headers, cookies=session['cookies'], timeout=current_app.config['API_TIMEOUT'], verify=False)
    except (ConnectionError, ConnectTimeout, ReadTimeout) as e:
        msg = str(e)
        return {"error": "{}".format(msg)}
    if not r.ok:
        if r.status_code == 401 and retry_counter == 0: # Unauthorized
            # Re-try only once bootstrapping a new token
            session['auth'] = bootstrap()
            return link_gateway(identifier, section, retry_counter=retry_counter+1)
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


class Abstract(Mapping):
    def __init__(self, identifier):
        self._storage = {}
        results = _abstract(identifier)
        docs = results.get('response', {}).get('docs', [])
        if not docs or len(docs) == 0:
            self._storage['error'] = "Record not found."
        else:
            self._storage.update(self._process(docs[0]))

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

    def _process(self, doc):
        """
        Sanitize and retreive complementary data
        """
        # Ensure title is a list
        if not isinstance(doc['title'], list):
            doc['title'] = [doc['title']]

        # Extract page from list
        if 'page' in doc and isinstance(doc['page'], list) and len(doc['page']) > 0:
            doc['page'] = doc['page'][0]

        if doc.get('data'):
            doc['data'] = self._process_data(doc['data'])

        # Parse publication date and store it as Month Year (e.g., September 2019)
        try:
            doc['pubdate'] = datetime.datetime.strptime(doc['pubdate'], '%Y-%m-00').strftime("%B %Y")
        except ValueError:
            pass

        # Find arXiv ID
        doc['arXiv'] = None
        for element in doc['identifier']:
            if element.startswith("arXiv:"):
                doc['arXiv'] = element
                break

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


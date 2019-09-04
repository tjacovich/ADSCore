import urllib.parse
from flask import session, current_app
from requests.exceptions import ConnectionError, ConnectTimeout, ReadTimeout
from adscore.constants import SEARCH_SERVICE, BOOTSTRAP_SERVICE, EXPORT_SERVICE, VAULT_SERVICE, OBJECTS_SERVICE, API_TIMEOUT


def bootstrap():
    """
    Get an anonymous token, if the user already has a session, the same token
    will be recovered from the API unless it has expired (in which case, a new
    renewed one will be received)
    """
    r = current_app.client.get(BOOTSTRAP_SERVICE, cookies=session['cookies'], timeout=API_TIMEOUT, verify=False)
    r.raise_for_status()
    r.cookies.clear_expired_cookies()
    session['cookies'].update(r.cookies.get_dict())
    auth = r.json()
    return { 'access_token': auth['access_token'], 'expire_in': auth['expire_in'] }

def abstract(identifier, retry_counter=0):
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
        r = current_app.client.get(SEARCH_SERVICE + "?" + params, headers=headers, cookies=session['cookies'], timeout=API_TIMEOUT, verify=False)
    except (ConnectionError, ConnectTimeout, ReadTimeout) as e:
        msg = str(e)
        return {"error": "{}".format(msg)}
    if not r.ok:
        if r.status_code == 401 and retry_counter == 0: # Unauthorized
            # Re-try only once bootstrapping a new token
            session['auth'] = bootstrap()
            return abstract(identifier, retry_counter=retry_counter+1)
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
    results = r.json()
    for i in range(len(results['response']['docs'])):
        results['response']['docs'][i]['reference_count'] = results['response']['docs'][i]['[citations]']['num_references']
    return results

def export_abstract(bibcode):
    """
    Export bibtex
    """
    headers = { "Authorization": "Bearer:{}".format(session['auth']['access_token']), }
    data = {
            'bibcode': ['{0}'.format(bibcode)],
            'sort': 'date desc, bibcode desc',
            }
    try:
        r = current_app.client.post(EXPORT_SERVICE, json=data, headers=headers, cookies=session['cookies'], timeout=API_TIMEOUT, verify=False)
    except (ConnectionError, ConnectTimeout, ReadTimeout) as e:
        msg = str(e)
        return {"error": "{}".format(msg)}
    if not r.ok:
        if r.status_code == 401 and retry_counter == 0: # Unauthorized
            # Re-try only once bootstrapping a new token
            session['auth'] = bootstrap()
            return export_abstract(bibcode, retry_counter=retry_counter+1)
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
    return r.json()

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
    r = current_app.client.post(VAULT_SERVICE, json=data, headers=headers, cookies=session['cookies'], timeout=API_TIMEOUT, verify=False)
    r.raise_for_status()
    r.cookies.clear_expired_cookies()
    session['cookies'].update(r.cookies.get_dict())
    return r.json()

def objects_query(object_names):
    """
    Transform object into ID
    """
    headers = { "Authorization": "Bearer:{}".format(session['auth']['access_token']) }
    data = {
                'query': ["object:({})".format(",".join(object_names))],
            }
    try:
        r = current_app.client.post(OBJECTS_SERVICE, json=data, headers=headers, cookies=session['cookies'], timeout=API_TIMEOUT, verify=False)
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
    return r.json()

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
                    'fl': 'title,bibcode,author,citation_count,pubdate,[citations],property,esources',
                    'q': '{0}'.format(q),
                    'rows': '{0}'.format(rows),
                    'sort': '{0}'.format(sort),
                    'start': '{0}'.format(start),
                    'stats': stats,
                    'stats.field': stats_field
                })
    try:
        r = current_app.client.get(SEARCH_SERVICE + "?" + params, headers=headers, cookies=session['cookies'], timeout=API_TIMEOUT, verify=False)
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
    results = r.json()
    for i in range(len(results['response']['docs'])):
        results['response']['docs'][i]['reference_count'] = results['response']['docs'][i]['[citations]']['num_references']
    return results


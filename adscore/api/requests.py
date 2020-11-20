import json
import urllib.parse
import flask
from flask import current_app, abort, g
import requests
from requests.exceptions import ConnectionError, ConnectTimeout, ReadTimeout

class RequestsManager:
    """
    It follows a kind of singleton design pattern where the instance is stored in
    flask g global variable, which is only global within the current request
    context.
    """

    @classmethod
    def init(cls, auth, cookies):
        g.manager_instance = RequestsManager.__RequestsManager(auth, cookies)

    @classmethod
    def is_initialized(cls):
        return "manager_instance" in g

    def __init__(self):
        if not RequestsManager.is_initialized():
            raise Exception("Request Manager needs to be initialized")

    def __getattr__(self, name):
        return getattr(g.manager_instance, name)

    class __RequestsManager(object):
        """
        Keeps track of authentication information used to issue requests to ADS API.
        """

        def __init__(self, auth, cookies):
            """
            Create an API object, bootstrap if auth is empty (it will use the provided
            cookies so that it can take into account any BBB session)
            """
            self.auth = auth
            self.cookies = cookies
            if not self.auth:
                self._bootstrap() # It will update self.auth

        def _bootstrap(self):
            """
            Get an anonymous token, if the user already has a session, the same token
            will be recovered from the API unless it has expired (in which case, a new
            renewed one will be received)
            """
            self.auth = {} # During bootstrap, make sure we do not bootstrap with an access token
            params = None
            bootstrap_response = self.request(current_app.config['BOOTSTRAP_SERVICE'], params,
                                 method="GET", retry_counter=0)
            if 'access_token' not in bootstrap_response or 'expire_in' not in bootstrap_response:
                abort(500, "Bootstrap returned invalid data")
            current_app.logger.info("Bootstrapped access token '%s'", bootstrap_response['access_token'])
            self.auth = { 'access_token': bootstrap_response['access_token'], 'expire_in': bootstrap_response['expire_in'], 'bot': False }

        def request(self, endpoint, params, method="GET", headers=None, retry_counter=0, json_format=True):
            """
            Execute query
            """
            if headers is None:
                new_headers = {}
            else:
                new_headers = headers.copy()

            if self.auth.get('access_token'):
                new_headers["Authorization"] = "Bearer:{}".format(self.auth['access_token'])
            new_headers['Accept'] = 'application/json; charset=utf-8'

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
                current_app.logger.debug("Dispatching '{}' request to endpoint '{}'".format(method, url))
                if current_app.config['REQUESTS_CONNECTION_POOL_ENABLED']:
                    r = getattr(current_app.client, method.lower())(url, json=data, headers=new_headers, cookies=self.cookies, timeout=current_app.config['API_TIMEOUT'], verify=False, allow_redirects=False)
                else:
                    if flask.has_request_context():
                        # Propagate key information from the original request
                        new_headers[u'X-Original-Uri'] = flask.request.headers.get(u'X-Original-Uri', u'-')
                        new_headers[u'X-Original-Forwarded-For'] = flask.request.headers.get(u'X-Original-Forwarded-For', u'-')
                        new_headers[u'X-Forwarded-For'] = flask.request.headers.get(u'X-Forwarded-For', u'-')
                        new_headers[u'X-Amzn-Trace-Id'] = flask.request.headers.get(u'X-Amzn-Trace-Id', '-')
                    r = getattr(requests, method.lower())(url, json=data, headers=new_headers, cookies=self.cookies, timeout=current_app.config['API_TIMEOUT'], verify=False, allow_redirects=False)
                current_app.logger.debug("Received response from endpoint '{}' with status code '{}'".format(url, r.status_code))
            except (ConnectionError, ConnectTimeout, ReadTimeout) as e:
                current_app.logger.exception("Exception while connecting to microservice")
                if retry_counter == 0:
                    current_app.logger.info("Re-trying connection to microservice")
                    return self.request(endpoint, params, method=method, headers=headers, retry_counter=retry_counter+1, json_format=json_format)
                else:
                    abort(502)
            except Exception as e:
                current_app.logger.exception("Exception (unexpected) while connecting to microservice")
                msg = str(e)
                return {"error": "{}".format(msg)}

            if not r.ok:
                if r.status_code == 401 and retry_counter == 0 and not self.auth.get('bot', False): # Unauthorized
                    # Re-try only once bootstrapping a new token
                    self._bootstrap() # It will update self.auth
                    current_app.logger.info("Re-trying connection to microservice after bootstrapping")
                    return self.request(endpoint, params, method=method, retry_counter=retry_counter+1, json_format=json_format)
                if r.status_code in (401, 429) or r.status_code >= 500:
                    # Unauthorized (401), too many requests (429), errors...
                    abort(r.status_code)
                try:
                    msg = r.json().get('error', {})
                    if type(msg) is dict:
                        msg = msg.get('msg', msg)
                    if len(msg) == 0:
                        # Try special case: reference resolver returns a 'reason' key with a json string that contains the 'error' message
                        msg = json.loads(r.json().get('reason', '{}')).get('error')
                except:
                    msg = r.content
                current_app.logger.debug("Response from endpoint '{}' ended with error message '{}'".format(url, msg))
                return {"error": "{} (HTTP status code {})".format(msg, r.status_code)}
            #r.raise_for_status()
            r.cookies.clear_expired_cookies()
            self.cookies.update(r.cookies.get_dict())
            if json_format:
                try:
                    results = r.json()
                except json.decoder.JSONDecodeError:
                    current_app.logger.exception("Exception while interpreting microservice JSON response for '%s'", url)
                    results = {"error": "Response is not JSON compatible: {}".format(r.content)}
                return results
            else:
                return {}


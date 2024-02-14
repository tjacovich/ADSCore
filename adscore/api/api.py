import urllib.parse
from flask import request, current_app
from .abstract import Abstract
from .search import Search
from .requests import RequestsManager

class API(object):
    def __init__(self):
        """
        Create an API object, bootstrap if auth is empty (it will use the provided
        cookies so that it can take into account any BBB session)
        """
        self.manager = RequestsManager()

    def search(self, q, rows=25, start=0, sort="date desc", fields="title,bibcode,author,citation_count,citation_count_norm,pubdate,[citations],property,esources,data,publisher"):
        return Search(q, rows=rows, start=start, sort=sort, fields=fields)

    def abstract(self, identifier):
        return Abstract(identifier)

    def store_query(self, bibcodes, sort="date desc, bibcode desc"):
        """
        Store query in vault
        """
        data = {
                    'bigquery': ["bibcode\n"+"\n".join(bibcodes)],
                    'fq': ["{!bitset}"],
                    'q': ["*:*"],
                    'sort': [sort]
                }
        return self.manager.request(current_app.config['VAULT_SERVICE'], data, method="POST", retry_counter=0)

    def objects_query(self, object_names, retry_counter=0):
        """
        Transform object into ID
        """
        data = {
                    'query': ["object:({})".format(",".join(object_names))],
                }
        return self.manager.request(current_app.config['OBJECTS_SERVICE'], data, method="POST", retry_counter=0)

    def link_gateway(self, identifier, section, retry_counter=0):
        """
        Log click
        """
        params = None
        headers = {}
        if request.user_agent.string:
            headers['User-Agent'] = request.user_agent.string
        if request.referrer:
            headers['referer'] = request.referrer
        return self.manager.request(current_app.config['LINKGATEWAY_SERVICE'] + identifier + "/" + section, params, method="GET", headers=headers, retry_counter=0, json_format=False)

    def resolve_reference(self, text):
        """
        Resolve a text reference into a bibcode
        """
        params = None
        text = urllib.parse.quote(text)
        return self.manager.request(current_app.config['REFERENCE_SERVICE']+"/"+text, params, method="GET", retry_counter=0)


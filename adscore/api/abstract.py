import json
from collections.abc import Mapping
from flask import current_app
from .requests import RequestsManager
from .search import Search

class Abstract(Mapping):
    def __init__(self, identifier):
        self.manager = RequestsManager()
        try:
            redis_client = current_app.extensions['redis']
            storage = redis_client.get(identifier)
            if storage:
                storage = json.loads(storage.decode('utf-8'))
        except Exception:
            current_app.logger.exception("Exception while restoring abstract results from cache")
            # Do not affect users if connection to Redis is lost in production
            if current_app.debug:
                raise
            storage = None
            redis_client = None
        if storage:
            self._storage = storage
        else:
            self._storage = {}
            docs = self._abstract(identifier)
            if docs and len(docs) > 0:
                self._storage.update(self._augment(docs[0]))
            else:
                self._storage['error'] = "Record not found."
            try:
                if redis_client:
                    redis_client.set(identifier, json.dumps(self._storage), ex=current_app.config['REDIS_EXPIRATION_TIME'])
            except Exception:
                current_app.logger.exception("Exception while storing abstract results to cache")
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
        associated = self._resolver(doc['bibcode'], resource="associated")
        if 'error' not in associated:
            doc['associated'] = associated.get('links', {}).get('records', [])
        else:
            doc['associated'] = []

        graphics = self._graphics(doc['bibcode'])
        if 'error' not in graphics:
            doc['graphics'] = graphics
        else:
            doc['graphics'] = []

        metrics = self._metrics(doc['bibcode'])
        if 'error' not in metrics and 'Error' not in metrics:
            doc['metrics'] = metrics
        else:
            doc['metrics'] = {}

        export = self._export(doc['bibcode'])
        if 'error' not in export:
            doc['export'] = export.get('export')
        else:
            doc['export'] = None

        return doc

    def _abstract(self, identifier):
        """
        Retrieve abstract
        """
        q = 'identifier:{0}'.format(identifier)
        fields = 'identifier,[citations],abstract,author,bibcode,bibstem,citation_count,comment,issn,isbn,doi,id,keyword,page,page_range,property,esources,pub,pub_raw,pubdate,pubnote,read_count,title,volume,data,issue,doctype'
        search = Search(q, rows=1, start=0, sort="date desc", fields=fields)
        return search.get('response', {}).get('docs', [])

    def _export(self, bibcode, retry_counter=0):
        """
        Export bibtex
        """
        data = {
                'bibcode': ['{0}'.format(bibcode)],
                'sort': 'date desc, bibcode desc',
                }
        return self.manager.request(current_app.config['EXPORT_SERVICE'], data, method="POST", retry_counter=0)

    def _resolver(self, identifier, resource="associated", retry_counter=0):
        """
        Retrieve associated works
        """
        params = None
        return self.manager.request(current_app.config['RESOLVER_SERVICE'] + identifier + "/" + resource, params, method="GET", retry_counter=0)

    def _graphics(self, identifier, retry_counter=0):
        """
        Retrieve graphics
        """
        params = None
        return self.manager.request(current_app.config['GRAPHICS_SERVICE'] + identifier, params, method="GET", retry_counter=0)

    def _metrics(self, bibcode):
        """
        Metrics
        """
        data = {
                'bibcodes': ['{0}'.format(bibcode)],
                }
        return self.manager.request(current_app.config['METRICS_SERVICE'], data, method="POST", retry_counter=0)


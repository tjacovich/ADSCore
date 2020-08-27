import json
import datetime
import functools
from collections.abc import Mapping
from flask import current_app
from .requests import RequestsManager

class Search(Mapping):
    def __init__(self, q, rows=25, start=0, sort="date desc", fields="title,bibcode,author,citation_count,citation_count_norm,pubdate,[citations],property,esources,data"):
        self.manager = RequestsManager()
        try:
            redis_client = current_app.extensions['redis']
            storage = redis_client.get("/".join((current_app.config['REDIS_DATA_KEY_PREFIX'], q, str(rows), str(start), sort, fields)))
            if storage:
                storage = json.loads(storage.decode('utf-8'))
        except Exception:
            current_app.logger.exception("Exception while recovering search results from cache")
            # Do not affect users if connection to Redis is lost in production
            if current_app.debug:
                raise
            storage = None
            redis_client = None
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
            if "object:" in q:
                # object: operator needs to be translated into the proper IDs
                # For instance, object:M67 translates into:
                #   ((=abs:M67 OR simbid:1136125 OR nedid:MESSIER_067)
                #    database:astronomy)
                r = self.manager.request(current_app.config['OBJECTS_SERVICE'], {'query': [q]}, method="POST", retry_counter=0)
                params['q'] = r.get('query', q)
            results = self._search(params)
            self._storage.update(self._process(results))
            try:
                if redis_client:
                    redis_client.set("/".join((current_app.config['REDIS_DATA_KEY_PREFIX'], q, str(rows), str(start), sort, fields)), json.dumps(self._storage), ex=current_app.config['REDIS_EXPIRATION_TIME'])
            except Exception:
                current_app.logger.exception("Exception while storing search results to cache")
                # Do not affect users if connection to Redis is lost in production
                if current_app.debug:
                    raise

    def _search(self, params):
        return self.manager.request(current_app.config['SEARCH_SERVICE'], params, method="GET", retry_counter=0)

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
            elif len(data_components) == 1:
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
                        results['response']['docs'][i]['formatted_alphanumeric_pubdate'] = datetime.datetime.strptime(results['response']['docs'][i]['pubdate'], '%Y-%m-00').strftime("%B %Y")
                        results['response']['docs'][i]['formatted_numeric_pubdate'] = datetime.datetime.strptime(results['response']['docs'][i]['pubdate'], '%Y-%m-00').strftime("%m/%Y")
                    except ValueError:
                        try:
                            results['response']['docs'][i]['formatted_alphanumeric_pubdate'] = datetime.datetime.strptime(results['response']['docs'][i]['pubdate'], '%Y-00-00').strftime("%Y")
                            results['response']['docs'][i]['formatted_numeric_pubdate'] = results['response']['docs'][i]['formatted_alphanumeric_pubdate']
                        except ValueError:
                            pass

                if 'page_range' in results['response']['docs'][i]:
                    pages = results['response']['docs'][i]['page_range'].split("-")
                    if len(pages) == 2:
                        results['response']['docs'][i]['last_page'] = pages[1]

                # Find arXiv ID
                if 'identifier' in results['response']['docs'][i]:
                    results['response']['docs'][i]['arXiv'] = None
                    for element in results['response']['docs'][i]['identifier']:
                        if element.startswith("arXiv:"):
                            results['response']['docs'][i]['arXiv'] = element
                            break
            return results


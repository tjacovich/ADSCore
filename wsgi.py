# -*- coding: utf-8 -*-
"""
    wsgi
    ~~~~

    entrypoint wsgi script
"""

from werkzeug.serving import run_simple
from werkzeug.wsgi import DispatcherMiddleware
from adscore import app as application
from werkzeug.middleware.http_proxy import ProxyMiddleware

if __name__ == "__main__":

    application = ProxyMiddleware(application, {
      "/v1": {
        "target": "https://devapi.adsabs.harvard.edu/"
      },
      "/styles": {
        "target": "https://ui.adsabs.harvard.edu/styles"
      }
    })

    run_simple(
        '0.0.0.0', 8000, application, use_reloader=False, use_debugger=True
    )

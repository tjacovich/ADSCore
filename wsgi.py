# -*- coding: utf-8 -*-
"""
    wsgi
    ~~~~

    entrypoint wsgi script
"""

from werkzeug.serving import run_simple
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.middleware.http_proxy import ProxyMiddleware
from adscore import app as application


if __name__ == "__main__":

    application = ProxyMiddleware(application, {
      "/static": {
        "target": "https://dev.adsabs.harvard.edu/static"
      },
      "/styles": {
        "target": "https://dev.adsabs.harvard.edu/styles"
      },
      "/libs": {
        "target": "https://dev.adsabs.harvard.edu/libs"
      },
      "/config": {
        "target": "https://dev.adsabs.harvard.edu/config"
      },
      "/js": {
        "target": "https://dev.adsabs.harvard.edu/js"
      },
      "/link_gateway": {
        "target": "https://dev.adsabs.harvard.edu/link_gateway"
      }
    })

    run_simple(
        '0.0.0.0', 8181, application, use_reloader=False, use_debugger=True
    )

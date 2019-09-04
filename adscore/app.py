import os
import sys
import requests
from flask import Flask
from flask_minify import minify
from adsmutils import ADSFlask

def create_app(**config):
    opath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if opath not in sys.path:
        sys.path.insert(0, opath)

    if config:
        app = ADSFlask(__name__, static_folder=None, local_config=config)
    else:
        app = ADSFlask(__name__, static_folder=None)

    app.url_map.strict_slashes = False

    if app.config['ENVIRONMENT'] != "localhost":
        minify(app=app, html=True, js=True, cssless=True, cache=True, fail_safe=True, bypass=[])

    return app

app = create_app()

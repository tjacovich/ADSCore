import time
import urllib.parse
from flask import render_template, session, request, redirect, g, current_app, url_for, abort
from adscore.app import app, limiter, redis_client, get_remote_address
from adscore.api import API, RequestsManager
from adscore import crawlers
from adscore.forms import ModernForm, PaperForm, ClassicForm
from adscore.tools import is_expired

def _url_for(*args, **kwargs):
    """
    When running in front of a ingress nginx, the correct protocol is HTTPS
    and not HTTP.
    """
    if current_app.config['ENVIRONMENT'] != "localhost":
        kwargs.update({'_external': True, '_scheme': 'https'})
    return url_for(*args, **kwargs)

@limiter.request_filter
def probes():
    """
    If the request is related to the readiness/liveness probe, do not rate limit.
    """
    return request.path in ('/ready', '/alive')

@limiter.request_filter
def header_whitelist():
    """
    If the request has an access token stored in the session, it means that the
    request sent a session cookie in the headers stored as requested by a previous
    request that was answered by ADS Core. The client is well behaving, storing
    cookies set by ADS Core and thus, we do not want to rate limit them.

    Rate limits are only to protect us from bootstrapping thousands of access
    tokens in the database.
    """
    if 'auth' in session:
        return True
    else:
        user_agent = request.headers.get('User-Agent')
        remote_ip = get_remote_address()
        #### For testing purposes:
        #user_agent = "Googlebot"
        #remote_ip = "66.249.66.1" # crawl-66-249-66-1.googlebot.com.
        #user_agent = "DuckDuckBot"
        #remote_ip = "50.16.241.117"
        #remote_ip = "127.0.0.1"
        evaluation = crawlers.evaluate(remote_ip, user_agent)

        if evaluation in (crawlers.VERIFIED_BOT, crawlers.UNVERIFIABLE_BOT, crawlers.POTENTIAL_MALICIOUS_BOT):
            return True
    return False

@app.before_request
def before_request():
    """
    Store API anonymous cookie in session or if it exists, check if it has expired
    """
    if request.path in ('/ready', '/alive'):
        # Do not bootstrap readiness/liveness probes
        return
    g.request_start_time = time.time()
    g.request_time = lambda: "{:.3f}s".format((time.time() - g.request_start_time))
    if 'cookies' not in session:
        session['cookies'] = {}

    if 'auth' not in session or is_expired(session['auth']):
        user_agent = request.headers.get('User-Agent')
        remote_ip = get_remote_address()
        #### For testing purposes:
        #user_agent = "Googlebot"
        #remote_ip = "66.249.66.1" # crawl-66-249-66-1.googlebot.com.
        #user_agent = "DuckDuckBot"
        #remote_ip = "50.16.241.117"
        #remote_ip = "127.0.0.1"
        evaluation = crawlers.evaluate(remote_ip, user_agent)
        if evaluation == crawlers.VERIFIED_BOT:
            # Extremely high rate limit
            RequestsManager.init(auth={'access_token': app.config['VERIFIED_BOTS_ACCESS_TOKEN'], 'expire_in': "2050-01-01T00:00:00", 'bot': True}, cookies={})
        elif evaluation == crawlers.UNVERIFIABLE_BOT:
            # Slightly higher rate limit
            RequestsManager.init(auth={'access_token': app.config['UNVERIFIABLE_BOTS_ACCESS_TOKEN'], 'expire_in': "2050-01-01T00:00:00", 'bot': True}, cookies={})
        elif evaluation == crawlers.POTENTIAL_MALICIOUS_BOT:
            # Rate limits as a regular user with the advantage that there is no bootstrap
            RequestsManager.init(auth={'access_token': app.config['MALICIOUS_BOTS_ACCESS_TOKEN'], 'expire_in': "2050-01-01T00:00:00", 'bot': True}, cookies={})

    if not RequestsManager.is_initialized():
        if request.cookies.get('session'):
            # - Re-use BBB session, if it is valid, the same BBB token will be returned by bootstrap
            # thus if the user was authenticated, it will use the user token
            # - Always bootstrap, otherwise the browser may end up logged in with different
            # users in BBB and core
            # - Ignore any previous bootstrapped access token
            RequestsManager.init(auth={}, cookies={'session': request.cookies.get('session')})
        elif 'auth' not in session:
            # No BBB or core session, API will bootstrap
            RequestsManager.init(auth={}, cookies={})
        else:
            # We have a core session and no BBB session, this is the only situation
            # API will not bootstrap
            RequestsManager.init(auth=session['auth'], cookies={})

@app.after_request
def after_request(response):
    # Store up-to-date auth data in cookie session
    if RequestsManager.is_initialized():
        manager = RequestsManager()
        session.clear()
        session['auth'] = manager.auth
    return response


@app.errorhandler(429)
def ratelimit_handler(e):
    if e.description.endswith('per 1 day'):
        # ADS Core limit hit (to limit too many bootstraps)
        remote_ip = get_remote_address()
        description = "We have received too many requests from your IP ({}).".format(remote_ip)
    else:
        # API ratelimit hit
        description = e.description
    user_agent = request.headers.get('User-Agent')
    remote_ip = get_remote_address()
    evaluation = crawlers.evaluate(remote_ip, user_agent)
    if evaluation == crawlers.VERIFIED_BOT:
        app.logger.info("Rate limited a request classified as 'VERIFIED_BOT'")
    elif evaluation == crawlers.UNVERIFIABLE_BOT:
        app.logger.info("Rate limited a request classified as 'UNVERIFIABLE_BOT'")
    elif evaluation == crawlers.POTENTIAL_MALICIOUS_BOT:
        app.logger.info("Rate limited a request classified as 'POTENTIAL_MALICIOUS_BOT'")
    elif evaluation == crawlers.POTENTIAL_USER:
        app.logger.info("Rate limited a request classified as 'POTENTIAL_USER'")
    else:
        # None
        app.logger.info("Rate limited a request not classified: '%s' - '%s'", remote_ip, user_agent)
    form = ModernForm()
    return _render_template('429.html', request_path=request.path[1:], form=form, code=429, description=description), 429

@app.errorhandler(404)
def page_not_found(e):
    form = ModernForm()
    return _render_template('404.html', request_path=request.path[1:], form=form, code=404), 404

@app.errorhandler(500)
def internal_error(e):
    form = ModernForm()
    return _render_template('500.html', request_path=request.path[1:], form=form, code=500), 500

@app.route(app.config['SERVER_BASE_URL']+'unavailable', methods=['GET', 'POST', 'PUT', 'DELETE'], strict_slashes=False)
@app.route(app.config['SERVER_BASE_URL']+'v1', methods=['GET', 'POST', 'PUT', 'DELETE'], strict_slashes=False)
@app.route(app.config['SERVER_BASE_URL']+'v1/<endpoint>', methods=['GET', 'POST', 'PUT', 'DELETE'], strict_slashes=False)
def unavailable(endpoint=None):
    """
    Endpoint to be used when the site needs to go into maintenance mode
    """
    form = ModernForm()
    return _render_template('503.html', request_path=request.path[1:], form=form, code=503), 503

@app.route(app.config['SERVER_BASE_URL'], methods=['GET'])
def index():
    """
    Modern form if no search parameters are sent, otherwise show search results
    """
    form = ModernForm(request.args)
    return _render_template('modern-form.html', form=form)

@app.route(app.config['SERVER_BASE_URL']+'search/<path:params>', methods=['GET'])
@app.route(app.config['SERVER_BASE_URL']+'search/', methods=['GET'])
def search(params=None):
    """
    Modern form if no search parameters are sent, otherwise show search results
    """
    form = ModernForm.parse(params or request.args)
    if form.p_.data > 0:
        # Redirect to correct the start parameter to match the requested page
        computed_start = (form.p_.data - 1) * form.rows.data
        if form.start.data != computed_start:
            return redirect(_url_for('search', q=form.q.data, sort=form.sort.data, rows=form.rows.data, start=computed_start))
    elif form.q.data and len(form.q.data) > 0:
        if not form.sort.raw_data:
            # There was not previous sorting specified
            if "similar(" in form.q.data or "trending(" in form.q.data:
                form.sort.data = "score desc"
            elif "references(" in form.q.data:
                form.sort.data = "first_author asc"
        api = API()
        results = api.search(form.q.data, rows=form.rows.data, start=form.start.data, sort=form.sort.data)
        qtime = "{:.3f}s".format(float(results.get('responseHeader', {}).get('QTime', 0)) / 1000)
        return _render_template('search-results.html', form=form, results=results.get('response'), stats=results.get('stats'), error=results.get('error'), qtime=qtime, sort_options=current_app.config['SORT_OPTIONS'])
    else:
        return redirect(_url_for('index'))

@app.route(app.config['SERVER_BASE_URL']+'classic-form', methods=['GET'], strict_slashes=False)
def classic_form():
    """
    Classic form if no search parameters are sent, otherwise process the parameters
    and redirect to the search results of a built query based on the parameters
    """
    form = ClassicForm(request.args)
    query = form.build_query()
    if query:
        return redirect(_url_for('search', q=query, sort=form.sort.data))
    else:
        return _render_template('classic-form.html', form=form, sort_options=current_app.config['SORT_OPTIONS'])

@app.route(app.config['SERVER_BASE_URL']+'paper-form', methods=['GET', 'POST'], strict_slashes=False)
def paper_form():
    """
    Paper form x if no search parameters are sent, otherwise process the parameters
    and redirect to the search results of a built query based on the parameters
    """

    if request.args.get('reference'): # GET
        # Middle form with reference query
        query = None
        form = PaperForm(request.args)
        api = API()
        results = api.resolve_reference(request.args.get('reference'))
        if results.get('resolved', {}).get('bibcode'):
            query = "bibcode:{}".format(results.get('resolved', {}).get('bibcode'))
        else:
            reference_error = "Error occurred resolving reference"
    else:
        reference_error = None
        if request.method == 'POST':
            # Bottom form with bibcode list
            form = PaperForm(request.form)
        else: # GET
            # Top form with fields
            form = PaperForm(request.args)
        query = form.build_query()
    if query:
        return redirect(_url_for('search', q=query))
    else:
        return _render_template('paper-form.html', form=form, reference_error=reference_error)

@app.route(app.config['SERVER_BASE_URL']+'public-libraries/<identifier>', methods=['GET'], strict_slashes=False)
def public_libraries(identifier):
    """
    Display public library
    """
    #return redirect(_url_for('search', q=f"docs(library/{identifier})"))
    return search(params=f"q=docs(library/{identifier})")

@app.route(app.config['SERVER_BASE_URL']+'abs/<path:alt_identifier>', methods=['GET'])
@app.route(app.config['SERVER_BASE_URL']+'abs/<identifier>/<section>', methods=['GET'])
@app.route(app.config['SERVER_BASE_URL']+'abs/<identifier>', methods=['GET'], strict_slashes=False)
def abs(identifier=None, section=None, alt_identifier=None):
    """
    Show abstract given an identifier
    """
    if not hasattr(abs, "sections"):
        # Initialize only once when the function abs() is called for the first time
        abs.sections = {
            "abstract": lambda identifier: _abstract(identifier),
            "citations": lambda identifier: _operation("citations", identifier),
            "references": lambda identifier: _operation("references", identifier),
            "coreads": lambda identifier: _operation("trending", identifier),
            "similar": lambda identifier: _operation("similar", identifier),
            "toc": lambda identifier: _toc(identifier),
            "exportcitation": lambda identifier: _export(identifier),
            "graphics": lambda identifier: _graphics(identifier),
            "metrics": lambda identifier: _metrics(identifier)
        }

    if identifier:
        if (section in abs.sections and len(identifier) < 15) or "*" in identifier or "?" in identifier:
            # - We do not have identifiers smaller than 15 characters,
            #   bibcodes are 19 (2020arXiv200410735B) and current arXiv are 16
            #   (arXiv:2004.10735)
            # - Identifiers do not contain wildcards (*, ?)
            abort(404)
            section in ("abstract", "citations", "references", "coreads")
        if section is None:
            return _abstract(identifier)
        elif section in abs.sections:
            return abs.sections[section](identifier)
        else:
            # An alternative identifier mistaken by a composition of id + section
            return _abstract(identifier+'/'+section)
    elif alt_identifier:
        if "*" in alt_identifier or "?" in alt_identifier:
            # - Identifiers do not contain wildcards (*, ?)
            abort(404)
        # Alternative identifiers such as DOIs (e.g., /abs/10.1051/0004-6361/201423945)
        return _abstract(alt_identifier)
    else:
        abort(404)

def _cached_render_template(key, *args, **kwargs):
    """
    Cache only the template rendering so that other parts of the code get executed
    such as connecting to link_gateway to register clicks
    """
    try:
        rendered_template = redis_client.get(key)
        if rendered_template:
            rendered_template = rendered_template.decode('utf-8')
    except Exception:
        # Do not affect users if connection to Redis is lost in production
        if app.debug:
            raise
        rendered_template = None

    if not rendered_template:
        rendered_template = _render_template(*args, **kwargs)

    try:
        redis_client.set(key, rendered_template, ex=app.config['REDIS_EXPIRATION_TIME'])
    except Exception:
        # Do not affect users if connection to Redis is lost in production
        if app.debug:
            raise
    return rendered_template

def _render_template(*args, **kwargs):
    """
    Wrapper to render template with multiple default variables
    """
    rendered_template = render_template(*args, **kwargs, environment=current_app.config['ENVIRONMENT'], base_url=app.config['SERVER_BASE_URL'], alert_message=current_app.config['ALERT_MESSAGE'], disable_full_ads_link=current_app.config['DISABLE_FULL_ADS_LINK'])
    return rendered_template

def _register_click():
    """
    Decides if a click needs to be registered.
    Returns True if the requests is not from a bot and it has a User-Agent
    that starts with the word Mozilla.
    """
    is_bot = session.get('auth', {}).get('bot', True)
    user_agent = request.headers.get('User-Agent')
    if not is_bot and user_agent and user_agent.startswith("Mozilla"):
        return True
    else:
        return False

def _abstract(identifier, section=None):
    api = API()
    doc = api.abstract(identifier)
    if 'bibcode' in doc:
        if doc['bibcode'] != identifier:
            target_url = _url_for('abs', identifier=doc['bibcode'], section='abstract')
            return redirect(target_url, code=301)
        if _register_click():
            api.link_gateway(doc['bibcode'], "abstract")
        key = "/".join((app.config['REDIS_RENDER_KEY_PREFIX'], identifier, 'abstract'))
        return _cached_render_template(key, 'abstract.html', doc=doc)
    else:
        abort(404)

def _operation(operation, identifier):
    api = API()
    doc = api.abstract(identifier)
    if 'bibcode' in doc:
        if _register_click():
            api.link_gateway(doc['bibcode'], operation)
        if operation in ("trending", "similar"):
            sort = "score desc"
        elif operation == "references":
            sort = "first_author asc"
        else:
            sort = "date desc"
        target_url = _url_for('search', q=f'{operation}(bibcode:{doc["bibcode"]})', sort=sort)
        if request.cookies.get('core', 'never') == 'always':
            return redirect(target_url)
        else:
            key = "/".join((app.config['REDIS_RENDER_KEY_PREFIX'], identifier, operation))
            return _cached_render_template(key, 'abstract-empty.html', doc=doc)
    else:
        abort(404)

def _toc(identifier):
    api = API()
    doc = api.abstract(identifier)
    if 'bibcode' in doc:
        if _register_click():
            api.link_gateway(doc['bibcode'], "toc")
        target_url = _url_for('search', q=f'bibcode:{doc["bibcode"][:13]}*')
        if request.cookies.get('core', 'never') == 'always':
            return redirect(target_url)
        else:
            key = "/".join((app.config['REDIS_RENDER_KEY_PREFIX'], identifier, 'toc'))
            return _cached_render_template(key, 'abstract-empty.html', doc=doc)
    else:
        abort(404)

def _export(identifier):
    """
    Export bibtex given an identifier
    """
    api = API()
    doc = api.abstract(identifier)
    if doc.get('export'):
        if 'bibcode' in doc and _register_click():
            api.link_gateway(doc['bibcode'], "exportcitation")
        key = "/".join((app.config['REDIS_RENDER_KEY_PREFIX'], identifier, 'export'))
        return _cached_render_template(key, 'abstract-export.html', doc=doc)
    else:
        abort(404)

def _graphics(identifier):
    """
    Graphics for a given identifier
    """
    api = API()
    doc = api.abstract(identifier)
    if len(doc.get('graphics', {}).get('figures', [])) > 0:
        if 'bibcode' in doc and _register_click():
            api.link_gateway(doc['bibcode'], "graphics")
        key = "/".join((app.config['REDIS_RENDER_KEY_PREFIX'], identifier, 'graphics'))
        return _cached_render_template(key, 'abstract-graphics.html', doc=doc)
    else:
        abort(404)

def _metrics(identifier):
    """
    Metrics for a given identifier
    """
    api = API()
    doc = api.abstract(identifier)
    if int(doc.get('metrics', {}).get('citation stats', {}).get('total number of citations', 0)) > 0 or int(doc.get('metrics', {}).get('basic stats', {}).get('total number of reads', 0)) > 0:
        if 'bibcode' in doc and _register_click():
            api.link_gateway(doc['bibcode'], "metrics")
        key = "/".join((app.config['REDIS_RENDER_KEY_PREFIX'], identifier, 'metrics'))
        return _cached_render_template(key, 'abstract-metrics.html', doc=doc)
    else:
        abort(404)

@app.route(app.config['SERVER_BASE_URL']+'core/always', methods=['GET'], strict_slashes=False)
@app.route(app.config['SERVER_BASE_URL']+'core/always/<path:url>', methods=['GET'])
def core_always(url=None):
    target_url = request.url_root + _build_full_ads_url(request, url)
    r = redirect(target_url)
    r.set_cookie('core', 'always')
    return r

@app.route(app.config['SERVER_BASE_URL']+'core/never', methods=['GET'], strict_slashes=False)
@app.route(app.config['SERVER_BASE_URL']+'core/never/<path:url>', methods=['GET'])
def core_never(url=None):
    target_url = request.url_root + _build_full_ads_url(request, url)
    r = redirect(target_url)
    r.set_cookie('core', 'never') # Keep cookie instead of deleting with r.delete_cookie('core')
    return r

@app.route(app.config['SERVER_BASE_URL']+'core/<path:url>', methods=['GET'])
@app.route(app.config['SERVER_BASE_URL']+'core/', methods=['GET'], strict_slashes=False)
def core(url=None):
    target_url = _build_full_ads_url(request, url)
    return _render_template('switch.html', request_path=request.path[1:], target_url=target_url)

def _build_full_ads_url(request, url):
    """
    Build full ADS url from a core request
    """
    full_url = ""
    params_dict = {}
    for accepted_param in ('q', 'rows', 'start', 'sort', 'p_'):
        if accepted_param in request.args:
            params_dict[accepted_param] = request.args.get(accepted_param)
    params = urllib.parse.urlencode(params_dict)
    if url:
        full_url += url
    if params:
        if len(full_url) >=1 and full_url[-1] != "/":
            full_url += "/"
        full_url += params
    return full_url

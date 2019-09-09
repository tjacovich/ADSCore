import time
import urllib
from flask import render_template, session, request, redirect, g, current_app, url_for, abort
from adscore.app import app
from adscore import api
from adscore.forms import ModernForm, PaperForm, ClassicForm
from adscore.tools import is_expired

@app.before_request
def before_request():
    """
    Store API anonymous cookie in session or if it exists, check if it has expired
    """
    g.request_start_time = time.time()
    g.request_time = lambda: "{:.3f}s".format((time.time() - g.request_start_time))
    if 'cookies' not in session:
        session['cookies'] = {}
    if request.cookies.get('session'):
        # Re-use BBB session, if it is valid, the same BBB token will be returned by bootstrap
        # thus if the user was authenticated, it will use the user token
        session['cookies']['session'] = request.cookies.get('session')
    if 'auth' not in session or is_expired(session['auth']):
        session['auth'] = api.bootstrap()

@app.errorhandler(404)
def page_not_found(e):
    form = ModernForm(request.args)
    return render_template('404.html', environment=current_app.config['ENVIRONMENT'], base_url=app.config['SERVER_BASE_URL'], auth=session['auth'], request_path=request.path[1:], form=form), 404

@app.route(app.config['SERVER_BASE_URL'], methods=['GET'])
def index():
    """
    Modern form if no search parameters are sent, otherwise show search results
    """
    form = ModernForm(request.args)
    return render_template('modern-form.html', environment=current_app.config['ENVIRONMENT'], base_url=app.config['SERVER_BASE_URL'], auth=session['auth'], form=form)


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
            return redirect(url_for('search', q=form.q.data, sort=form.sort.data, rows=form.rows.data, start=computed_start))
    elif form.q.data and len(form.q.data) > 0:
        results = api.search(form.q.data, rows=form.rows.data, start=form.start.data, sort=form.sort.data)
        qtime = "{:.3f}s".format(float(results.get('responseHeader', {}).get('QTime', 0)) / 1000)
        return render_template('search-results.html', environment=current_app.config['ENVIRONMENT'], base_url=app.config['SERVER_BASE_URL'], auth=session['auth'], form=form, results=results.get('response'), stats=results.get('stats'), error=results.get('error'), qtime=qtime, sort_options=current_app.config['SORT_OPTIONS'])
    else:
        return redirect(url_for('index'))

@app.route(app.config['SERVER_BASE_URL']+'classic-form', methods=['GET'], strict_slashes=False)
def classic_form():
    """
    Classic form if no search parameters are sent, otherwise process the parameters
    and redirect to the search results of a built query based on the parameters
    """
    form = ClassicForm(request.args)
    query = form.build_query()
    if query:
        return redirect(url_for('search', q=query))
    else:
        return render_template('classic-form.html', environment=current_app.config['ENVIRONMENT'], base_url=app.config['SERVER_BASE_URL'], auth=session['auth'], form=form)

@app.route(app.config['SERVER_BASE_URL']+'paper-form', methods=['GET', 'POST'], strict_slashes=False)
def paper_form():
    """
    Paper form x if no search parameters are sent, otherwise process the parameters
    and redirect to the search results of a built query based on the parameters
    """
    if request.method == 'POST':
        # Right form with bibcode list
        form = PaperForm(request.form)
    else: # GET
        # Left form with fields
        form = PaperForm(request.args)
    query = form.build_query()
    if query:
        return redirect(url_for('search', q=query))
    else:
        return render_template('paper-form.html', environment=current_app.config['ENVIRONMENT'], base_url=app.config['SERVER_BASE_URL'], auth=session['auth'], form=form)

@app.route(app.config['SERVER_BASE_URL']+'public-libraries/<identifier>', methods=['GET'], strict_slashes=False)
def public_libraries(identifier):
    """
    Display public library
    """
    #return redirect(url_for('search', q=f"docs(library/{identifier})"))
    return search(params=f"q=docs(library/{identifier})")

@app.route(app.config['SERVER_BASE_URL']+'abs/<identifier>/<section>', methods=['GET'])
@app.route(app.config['SERVER_BASE_URL']+'abs/<identifier>', methods=['GET'], strict_slashes=False)
def abs(identifier, section=None):
    """
    Show abstract given an identifier
    """
    if section in (None, "abstract"):
        return _abstract(identifier)
    elif section == "citations":
        return _operation("citations", identifier)
    elif section == "references":
        return _operation("references", identifier)
    elif section == "coreads":
        return _operation("trending", identifier)
    elif section == "similar":
        return _operation("similar", identifier)
    elif section == "toc":
        return _toc(identifier)
    elif section == "exportcitation":
        return _export(identifier)
    elif section == "graphics":
        return _graphics(identifier)
    elif section == "metrics":
        return _metrics(identifier)
    else:
        abort(404)

def _abstract(identifier, section=None):
    doc = api.Abstract(identifier)
    if 'bibcode' in doc:
        api.link_gateway(doc['bibcode'], "abstract")
        return render_template('abstract.html', environment=current_app.config['ENVIRONMENT'], base_url=app.config['SERVER_BASE_URL'], auth=session['auth'], doc=doc)
    else:
        abort(404)

def _operation(operation, identifier):
    doc = api.Abstract(identifier)
    if 'bibcode' in doc:
        api.link_gateway(doc['bibcode'], operation)
        target_url = url_for('search', q=f'{operation}(bibcode:{doc["bibcode"]})')
        return redirect(target_url)
    else:
        abort(404)

def _toc(identifier):
    doc = api.Abstract(identifier)
    if 'bibcode' in doc:
        api.link_gateway(doc['bibcode'], "toc")
        target_url = url_for('search', q=f'bibcode:{doc["bibcode"][:13]}*')
        return redirect(target_url)
    else:
        abort(404)

def _export(identifier):
    """
    Export bibtex given an identifier
    """
    doc = api.Abstract(identifier)
    if doc.get('export'):
        if 'bibcode' in doc:
            api.link_gateway(doc['bibcode'], "exportcitation")
        return render_template('abstract-export.html', environment=current_app.config['ENVIRONMENT'], base_url=app.config['SERVER_BASE_URL'], auth=session['auth'], doc=doc)
    else:
        abort(404)

def _graphics(identifier):
    """
    Graphics for a given identifier
    """
    doc = api.Abstract(identifier)
    if len(doc.get('graphics', {}).get('figures', [])) > 0:
        if 'bibcode' in doc:
            api.link_gateway(doc['bibcode'], "graphics")
        return render_template('abstract-graphics.html', environment=current_app.config['ENVIRONMENT'], base_url=app.config['SERVER_BASE_URL'], auth=session['auth'], doc=doc, error=results.get('error'))
    else:
        abort(404)

def _metrics(identifier):
    """
    Metrics for a given identifier
    """
    doc = api.Abstract(identifier)
    if int(doc.get('metrics', {}).get('citation stats', {}).get('total number of citations', 0)) > 0 or int(doc.get('metrics', {}).get('basic stats', {}).get('total number of reads', 0)) > 0:
        if 'bibcode' in doc:
            api.link_gateway(doc['bibcode'], "metrics")
        return render_template('abstract-metrics.html', environment=current_app.config['ENVIRONMENT'], base_url=app.config['SERVER_BASE_URL'], auth=session['auth'], doc=doc, error=results.get('error'))
    else:
        abort(404)

@app.route(app.config['SERVER_BASE_URL']+'core/always', methods=['GET'], strict_slashes=False)
@app.route(app.config['SERVER_BASE_URL']+'core/always/<path:url>', methods=['GET'])
def core_always(url=None):
    target_url = _build_full_ads_url(request, url)
    r = redirect(target_url)
    r.set_cookie('core', 'always')
    return r

@app.route(app.config['SERVER_BASE_URL']+'core/never', methods=['GET'], strict_slashes=False)
@app.route(app.config['SERVER_BASE_URL']+'core/never/<path:url>', methods=['GET'])
def core_never(url=None):
    target_url = _build_full_ads_url(request, url)
    r = redirect(target_url)
    r.set_cookie('core', 'never') # Keep cookie instead of deleting with r.delete_cookie('core')
    return r

def _build_full_ads_url(request, url):
    """
    Build full ADS url from a core request
    """
    full_url = request.url_root
    params_dict = {}
    for accepted_param in ('q', 'rows', 'start', 'sort', 'p_'):
        if accepted_param in request.args:
            params_dict[accepted_param] = request.args.get(accepted_param)
    params = urllib.parse.urlencode(params_dict)
    if url:
        full_url += url
    if params:
        if full_url[-1] != "/":
            full_url += "/"
        full_url += params
    return full_url

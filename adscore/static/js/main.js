(function() {
  // turn off no-js if we have javascript
  document.documentElement.className = document.documentElement.className.replace("no-js", "js");

  function getCookie(cname) {
    var name = cname + "=";
    var decodedCookie = decodeURIComponent(document.cookie);
    var ca = decodedCookie.split(';');
    for (var i = 0; i < ca.length; i++) {
      var c = ca[i];
      while (c.charAt(0) == ' ') {
        c = c.substring(1);
      }
      if (c.indexOf(name) == 0) {
        return c.substring(name.length, c.length);
      }
    }
    return "";
  }

  // continuously checks for presence of core cookie, if it finds it
  // it sets the flag on the document <html> element class list
  (function checkCookie() {
    const doc = document.documentElement;
    const hasCore = doc.classList.contains('core');
    const cookie = getCookie('core');
    if (cookie !== '' && !hasCore) {
      doc.className += ' core';
    } else if (!cookie && hasCore) {
      doc.className = doc.className.replace(' core', '');
    }
    setTimeout(checkCookie, 1000);
  })();

  // called at the bottom of the document,
  // will watch for changes to the core class on the doc element
  // before it will run
  window.startApp = function(page, data) {
    if (document.documentElement.classList.contains('core')) {
      window.setTimeout(window.startApp, 5000, page, data);
      return;
    }
    window.APP_VERSION = 'v1.2.27';
    const BASEURL = 'https://ui.adsabs.harvard.edu/';

    if (page === 'search' && data) {
      const params = Object.keys(data).map(function(key) {
        if (key === 'start') {
          return 'p_=' + (data.start / data.rows).toFixed();
        }
        return key + '=' + encodeURIComponent(data[key]);
      });
      window.location.href = BASEURL + 'search/' + params.join('&');
    } else if (page === 'abs') {
      window.__PRERENDERED = true;
    }

    const addScript = function(args) {
      let script = '<script type="text/javascript" ';
      script += Object.keys(args).map(function(arg) {
        return arg + '=' + args[arg];
      }).join(' ');
      document.write(script + '></script>');
    }

    addScript({
      src: BASEURL + 'libs/requirejs/require.js',
      id: 'requirescript'
    });
    document.getElementById('requirescript').onload = function() {
      require.config({
        baseUrl: BASEURL
      });

      /*
        Dynamically pick which configuration to use based on the url.
        Then attempt to load the resource, using require, upon failure we
        load a known resource (discovery.config.js)
      */
      var paths = {
        '': 'landing-page',
        'search': 'search-page',
        'abs': 'abstract-page'
      };

      var load;
      var version = window.APP_VERSION ? '?v=' + window.APP_VERSION : '';
      try {
        var loc = window.location;
        var parts = loc[loc.pathname === '/' ? 'hash' : 'pathname'].replace(/#/g, '').split('/');
        var path = parts.reverse().filter(function(p) {
          return Object.keys(paths).indexOf(p) > -1;
        });
        path = path.length && path[0];
        load = function() {
          // attempt to get bundle config
          require([BASEURL + paths[path] + '.config.js' + version], function() {}, function() {
            // on failure to load specific bundle; load generic one
            require([BASEURL + 'discovery.config.js' + version]);
          });
        };
      } catch (e) {
        load = function() {
          // on errors, just fallback to normal config
          require([BASEURL + 'discovery.config.js' + version]);
        };
      }

      (function checkLoad() {
        if (window.requirejs && typeof load === 'function') {
          return load();
        }
        setTimeout(checkLoad, 10);
      })();
    }
  }
})();

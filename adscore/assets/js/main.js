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

  (function() {

    // looks for the cookie, and sets true if its 'always'
    const coreCookie = getCookie('core') === 'always';

    // only load bumblebee if we detect the core cookie and we are on abstract page
    if (coreCookie || (!(/^\/abs\//.test(document.location.pathname)) && !coreCookie)) {
      return;
    }

    window.APP_VERSION = 'v1.2.30';
    window.__PRERENDERED = true;
    const BASEURL = 'https://dev.adsabs.harvard.edu/';

    const addScript = function(args, cb) {
      const script = document.createElement('script');
      Object.keys(args).forEach((key) => {
        script.setAttribute(key, args[key]);
      });
      script.onload = () => cb(script);
      document.body.appendChild(script);
    }

    addScript({
      src: BASEURL + 'libs/requirejs/require.js'
    }, () => {
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
    });
  })();
})();
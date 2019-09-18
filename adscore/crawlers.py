from flask import current_app
import socket

GOOGLE = 'google.com'
GOOGLEBOT = 'googlebot.com'
BING = 'search.msn.com'
YAHOO = 'crawl.yahoo.net'
BAIDU_COM = 'crawl.baidu.com'
BAIDU_JP = 'crawl.baidu.jp'
YANDEX_RU = 'yandex.ru'
YANDEX_NET = 'yandex.net'
YANDEX_COM = 'yandex.com'
ALEXA = 'alexa.com'

SEARCH_ENGINE_BOTS = {
                        "googlebot": {
                            'type': 'DNS',
                            'DNS': [GOOGLE, GOOGLEBOT]
                        },
                        "adsbot-google": {
                            'type': 'DNS',
                            'DNS': [GOOGLE, GOOGLEBOT]
                        },
                        "mediapartners-google": {
                            'type': 'DNS',
                            'DNS': [GOOGLE, GOOGLEBOT]
                        },
                        "feedfetcher-google": {
                            'type': 'DNS',
                            'DNS': [GOOGLE, GOOGLEBOT]
                        },
                        "AdsBot-Google-Mobile-Apps": {
                            'type': 'DNS',
                            'DNS': [GOOGLE, GOOGLEBOT]
                        },
                        "bingbot": {
                            'type': 'DNS',
                            'DNS': [BING]
                        },
                        "bingpreview": {
                            'type': 'DNS',
                            'DNS': [BING]
                        },
                        "msnbot": {
                            'type': 'DNS',
                            'DNS': [BING]
                        },
                        "slurp": {
                            'type': 'DNS',
                            'DNS': [YAHOO]
                        },
                        "duckduckbot": {
                            'type': 'IPs',
                            'IPs': [
                                # https://help.duckduckgo.com/duckduckgo-help-pages/results/duckduckbot/
                                '50.16.241.113',
                                '50.16.241.114',
                                '50.16.241.117',
                                '50.16.247.234',
                                '52.204.97.54',
                                '52.5.190.19',
                                '54.197.234.188',
                                '54.208.100.253',
                                '23.21.227.69',
                            ]
                        },
                        "baidu": {
                            'type': 'DNS',
                            'DNS': [BAIDU_COM, BAIDU_JP]
                        },
                        "yandex": {
                            'DNS': [YANDEX_RU, YANDEX_NET, YANDEX_COM]
                        },
                        "ia_archiver": {
                            'DNS': [ALEXA]
                        },
                        "facebot": {
                            'type': 'Unverifiable',
                        },
                        "facebookexternalhit": {
                            'type': 'Unverifiable',
                        },
                        "aolbuild": {
                            'type': 'Unverifiable',
                        },
                        "slackbot": {
                            'type': 'Unverifiable',
                        },
                        "slack-imgproxy": {
                            'type': 'Unverifiable',
                        },
                        "twitterbot": {
                            'type': 'Unverifiable',
                        },
                        "bot": {
                            'type': 'Unverifiable',
                        },
}

VERIFIED_BOT = 0
UNVERIFIABLE_BOT = 1
POTENTIAL_MALICIOUS_BOT = 2
POTENTIAL_USER = 3

def evaluate(remote_ip, user_agent):
    """
    Given a remote IP and user agent, determine if it is:
    - A verified bot
    - An unverifiable bot
    - A potentially malicious bot
    - A potential legitivate user
    """
    if user_agent is None:
        user_agent = ""
    try:
        cache = list(current_app.extensions['cache'].keys())[0]
        result = cache.get("/".join((current_app.config['CACHE_BOT_KEY_PREFIX'], remote_ip, user_agent)))
    except Exception:
        current_app.logger.exception("Recovering bot results from cache")
        result = None
        # Do not affect users if connection to Redis is lost in production
        if current_app.debug:
            raise
    if result is None:
        result = _classify(remote_ip, user_agent)
        try:
            if cache:
                cache.set("/".join((current_app.config['CACHE_BOT_KEY_PREFIX'], remote_ip, user_agent)), result)
        except Exception:
            current_app.logger.exception("Storing bot results to cache")
            # Do not affect users if connection to Redis is lost in production
            if current_app.debug:
                raise
    return result

def _classify(remote_ip, user_agent):
    bot_name, bot_verification_data = _find_bot(user_agent)
    if bot_name:
        if bot_verification_data.get('type') == 'Unverifiable':
            check_results = UNVERIFIABLE_BOT
            current_app.logger.info("Classified as 'UNVERIFIABLE_BOT'")
        elif _verify_bot(remote_ip, bot_verification_data):
            check_results = VERIFIED_BOT
            current_app.logger.info("Classified as 'VERIFIED_BOT'")
        else:
            check_results = POTENTIAL_MALICIOUS_BOT
            current_app.logger.info("Classified as 'POTENTIAL_MALICIOUS_BOT'")
    else:
        check_results = POTENTIAL_USER
        current_app.logger.info("Classified as 'POTENTIAL_USER'")
    return check_results

def _find_bot(user_agent):
    if isinstance(user_agent, str):
        user_agent = user_agent.lower()
        for k, v in SEARCH_ENGINE_BOTS.items():
            if k in user_agent:
                return k, v
    return None, None

def _verify_bot(remote_ip, bot_verification_data):
    """
    Verify bot using reverse/forward DNS resolution or IP whitelists
    """
    bot_type = bot_verification_data.get('type', 'Unverifiable')
    if bot_type == "DNS":
        search_engine_bot_domains = bot_verification_data.get('DNS')
        if search_engine_bot_domains:
            try:
                return _verify_dns(remote_ip, search_engine_bot_domains)
            except Exception:
                current_app.logger.exception("Reverse/forward resolving IP")
                return False
    elif bot_type == "IPs":
        search_engine_bot_ips = bot_verification_data.get('IPs')
        if search_engine_bot_ips:
            return _verify_ip(remote_ip, search_engine_bot_ips)
    return False

def _verify_ip(remote_ip, search_engine_bot_ips):
    """
    Check if remote IP is in the list of allowed IPs
    """
    for search_engine_bot_ip in search_engine_bot_ips:
        if search_engine_bot_ip == remote_ip:
            return True
    return False

def _verify_dns(remote_ip, search_engine_bot_domains):
    """
    Reverse resolve IP into its domain, check if it is a subdomain of a search
    engine bot and verify that when the domain is resolved forward into an IP
    it coincides with the original IP.
    """
    name, aliaslist, _addresslist = socket.gethostbyaddr(remote_ip)
    for hostname in [name] + aliaslist:
        for search_engine_bot_domain in search_engine_bot_domains:
            ndots = search_engine_bot_domain.count('.') # 'googlebot.com' => 1 dot => 2 levels
            hostname_domain = ".".join(name.split('.')[-ndots-1:]) # 'crawl-66-249-66-1.googlebot.com' => 'googlebot.com'
            if hostname_domain == search_engine_bot_domain:
                _name, _aliaslist, addresslist = socket.gethostbyname_ex(hostname)
                if remote_ip in addresslist:
                    return True
    return False


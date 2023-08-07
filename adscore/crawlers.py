from flask import current_app
import dns.name
import dns.reversename
import dns.resolver
import dns.exception
from collections import OrderedDict

GOOGLE = dns.name.from_text('google.com')
GOOGLEBOT = dns.name.from_text('googlebot.com')
APPLEBOT = dns.name.from_text('applebot.apple.com')
BING = dns.name.from_text('search.msn.com')
YAHOO = dns.name.from_text('crawl.yahoo.net')
BAIDU_COM = dns.name.from_text('crawl.baidu.com')
BAIDU_JP = dns.name.from_text('crawl.baidu.jp')
YANDEX_RU = dns.name.from_text('yandex.ru')
YANDEX_NET = dns.name.from_text('yandex.net')
YANDEX_COM = dns.name.from_text('yandex.com')
ALEXA = dns.name.from_text('alexa.com')

SEARCH_ENGINE_BOTS = OrderedDict([
                        ("googlebot", {
                            'type': 'DNS',
                            'DNS': [GOOGLE, GOOGLEBOT]
                        }),
                        ("googledocs", {
                            'type': 'DNS',
                            'DNS': [GOOGLE, GOOGLEBOT]
                        }),
                        ("adsbot-google", {
                            'type': 'DNS',
                            'DNS': [GOOGLE, GOOGLEBOT]
                        }),
                        ("applebot", {
                            'type': 'DNS',
                            'DNS': [APPLEBOT]
                        }),
                        ("mediapartners-google", {
                            'type': 'DNS',
                            'DNS': [GOOGLE, GOOGLEBOT]
                        }),
                        ("feedfetcher-google", {
                            'type': 'DNS',
                            'DNS': [GOOGLE, GOOGLEBOT]
                        }),
                        ("AdsBot-Google-Mobile-Apps", {
                            'type': 'DNS',
                            'DNS': [GOOGLE, GOOGLEBOT]
                        }),
                        ("bingbot", {
                            'type': 'DNS',
                            'DNS': [BING]
                        }),
                        ("bingpreview", {
                            'type': 'DNS',
                            'DNS': [BING]
                        }),
                        ("msnbot", {
                            'type': 'DNS',
                            'DNS': [BING]
                        }),
                        ("slurp", {
                            'type': 'DNS',
                            'DNS': [YAHOO]
                        }),
                        ("duckduckbot", {
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
                        }),
                        ("baidu", {
                            'type': 'DNS',
                            'DNS': [BAIDU_COM, BAIDU_JP]
                        }),
                        ("yandex", {
                            'DNS': [YANDEX_RU, YANDEX_NET, YANDEX_COM]
                        }),
                        ("ia_archiver", {
                            'DNS': [ALEXA]
                        }),
                        ("facebot", {
                            'type': 'Unverifiable',
                        }),
                        ("facebookexternalhit", {
                            'type': 'Unverifiable',
                        }),
                        ("aolbuild", {
                            'type': 'Unverifiable',
                        }),
                        ("slackbot", {
                            'type': 'Unverifiable',
                        }),
                        ("slack-imgproxy", {
                            'type': 'Unverifiable',
                        }),
                        ("twitterbot", {
                            'type': 'Unverifiable',
                        }),
                        ("bot", {
                            'type': 'Unverifiable',
                        }),
                        ("GPTbot", {
                            'type': 'IPs',
                            'IPs': [
                                # https://openai.com/gptbot-ranges.txt
                                '40.83.2.64',
                            ]
                        }),
])

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

    if not remote_ip:
        return UNVERIFIABLE_BOT

    if not isinstance(remote_ip, str):
        return UNVERIFIABLE_BOT

    remote_ip = remote_ip.strip()


    try:
        redis_client = current_app.extensions['redis']
        result = redis_client.get("/".join((current_app.config['REDIS_REQUESTS_KEY_PREFIX'], remote_ip, user_agent)))
        if result:
            result = int(result.decode('utf-8'))
    except Exception:
        current_app.logger.exception("Exception while recovering bot results from cache")
        result = None
        redis_client = None
        # Do not affect users if connection to Redis is lost in production
        if current_app.debug:
            raise
    if result is None or result not in (VERIFIED_BOT, UNVERIFIABLE_BOT, POTENTIAL_MALICIOUS_BOT, POTENTIAL_USER):
        result = _classify(remote_ip, user_agent)
        try:
            if redis_client:
                redis_client.set("/".join((current_app.config['REDIS_REQUESTS_KEY_PREFIX'], remote_ip, user_agent)), result, ex=current_app.config['REDIS_EXPIRATION_TIME'])
        except Exception:
            current_app.logger.exception("Exception while storing bot results to cache")
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
                return _verify_dns(remote_ip, search_engine_bot_domains, retry_counter=0)
            except:
                current_app.logger.exception("Exception while reverse/forward resolving IP remote_ip='{}'".format(remote_ip))
            else:
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

def _verify_dns(remote_ip, search_engine_bot_domains, retry_counter=0):
    try:
        return _resolve(remote_ip, search_engine_bot_domains)
    except dns.resolver.NXDOMAIN:
        # No domain name associated to IP
        return False
    except (dns.resolver.NoNameservers, dns.exception.Timeout):
        if retry_counter == 0:
            # Retry once
            return _verify_dns(remote_ip, search_engine_bot_domains, retry_counter=retry_counter+1)
        else:
            current_app.logger.exception("Exception while reverse/forward resolving IP")
            return False

def _resolve(remote_ip, search_engine_bot_domains):
    """
    Reverse resolve IP into its domain, check if it is a subdomain of a search
    engine bot and verify that when the domain is resolved forward into an IP
    it coincides with the original IP.
    """
    resolver = dns.resolver.Resolver()
    # The total number of seconds to spend trying to get an answer to the question:
    resolver.lifetime = current_app.config['DNS_LIFETIME']
    # The number of seconds to wait for a response from a server, before timing out:
    resolver.timeout = current_app.config['DNS_TIMEOUT']
    for ptr_record in resolver.query(dns.reversename.from_address(remote_ip), "PTR"):
        for search_engine_bot_domain in search_engine_bot_domains:
            if dns.name.from_text(ptr_record.to_text()).is_subdomain(search_engine_bot_domain):
                for remote_ip_check in resolver.query(ptr_record.to_text(), "A"):
                    remote_ip_coincides = remote_ip_check.to_text() == remote_ip
                    if remote_ip_coincides:
                        return True
    return False


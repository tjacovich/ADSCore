from adscore import crawlers
from adscore.tests import ADSCoreTestCase
import unittest

class TestGoogleBot(ADSCoreTestCase):
    def test_classify(self):
        for ip in (' 66.249.66.145', ' 66.249.66.143', ' 66.249.66.149', ' 66.249.66.147'):
            for ua in ('Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2272.96 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
                       'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'):
                assert crawlers.evaluate(ip, ua) == crawlers.VERIFIED_BOT
                
        for ip in ('128.101.175.19',):
            for ua in ('Mozilla/5.0 (Linux; Android 6.0.1; Nexus 5X Build/MMB29P) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2272.96 Mobile Safari/537.36 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
                       'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'):
                assert crawlers.evaluate(ip, ua) == crawlers.POTENTIAL_MALICIOUS_BOT
                

if __name__ == '__main__':
    unittest.main()
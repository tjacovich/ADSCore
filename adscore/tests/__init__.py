from flask_testing import TestCase

class ADSCoreTestCase(TestCase):
    """
    Base test class for when databases are being used.
    """

    def create_app(self):
        '''Start the wsgi application'''
        from adscore import create_app
        a = create_app(**{
            
            'TESTING': True,
            'PROPAGATE_EXCEPTIONS': True,
            'TRAP_BAD_REQUEST_ERRORS': True
        })
        return a

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        pass

    def tearDown(self):
        pass
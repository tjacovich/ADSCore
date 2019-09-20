import redis
import fakeredis

class FlaskRedisPool(object):
    def __init__(self, app=None):
        self.connection_pool = None
        self.fake_redis = None

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        redis_url = app.config.get("REDIS_URL", "redis://localhost:6379/0")
        if redis_url.startswith("fakeredis://"):
            self.fake_redis = fakeredis.FakeStrictRedis()
        else:
            max_connections = app.config['REDIS_POOL_MAX_CONNECTIONS']
            timeout = app.config['REDIS_TIMEOUT']
            self.connection_pool = redis.BlockingConnectionPool.from_url(redis_url, max_connections=max_connections, timeout=timeout, socket_timeout=timeout, socket_connect_timeout=timeout, encoding='utf-8',)

        if not hasattr(app, "extensions"):
            app.extensions = {}
        app.extensions['redis'] = self

    def __getattr__(self, name):
        if self.fake_redis:
            return getattr(self.fake_redis, name)
        else:
            return getattr(redis.StrictRedis(connection_pool=self.connection_pool), name)

    def __getitem__(self, name):
        if self.fake_redis:
            return self.fake_redis[name]
        else:
            return redis.StrictRedis(connection_pool=self.connection_pool)[name]

    def __setitem__(self, name, value):
        if self.fake_redis:
            self.fake_redis[name] = value
        else:
            redis.StrictRedis(connection_pool=self.connection_pool)[name] = value

    def __delitem__(self, name):
        if self.fake_redis:
            del self.fake_redis[name]
        else:
            del redis.StrictRedis(connection_pool=self.connection_pool)[name]


"""
config.py

Configuration and settings
"""
import os


def from_env(env_var, default):
    """
    Gets value from envrionment variable or uses default

    Args:
        env_var: name of envrionment variable
        default: the default value
    """
    new = os.environ.get(env_var)
    if new:
        return new
    else:
        return default


class Config(object):
    DEBUG = False
    TESTING = False

    SUBSCRIBERS = 'hermes_subscribers'
    SUBSCRIPTIONS = 'hermes_subscriptions'
    LOG = 'hermes_log'

    DB_URL = from_env("DB_URL", "https://dynamodb.eu-west-1.amazonaws.com")
    ROOT_URL = from_env("MEERKAT_HERMES_ROOT", "/hermes")

    SENDER = 'Notifications <notifications@emro.info>'
    CHARSET = 'UTF-8'
    FROM = 'Meerkat'

    API_KEY = "test-hermes"

    PUBLISH_RATE_LIMIT = 20
    CALL_TIMES = []


class Production(Config):
    DEBUG = True
    TESTING = False


class Development(Config):
    DEBUG = True
    TESTING = True


class Testing(Config):
    DEBUG = False
    TESTING = True
    SUBSCRIBERS = 'test_hermes_subscribers'
    SUBSCRIPTIONS = 'test_hermes_subscriptions'
    LOG = 'test_hermes_log'

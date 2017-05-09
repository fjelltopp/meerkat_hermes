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
    PRODUCTION = False

    SUBSCRIBERS = 'hermes_subscribers'
    SUBSCRIPTIONS = 'hermes_subscriptions'
    LOG = 'hermes_log'

    DB_URL = from_env("DB_URL", "http://dynamodb:8000")
    ROOT_URL = from_env("MEERKAT_HERMES_ROOT", "/hermes")

    SENDER = 'Notifications <notifications@emro.info>'
    CHARSET = 'UTF-8'
    FROM = 'Meerkat'

    API_KEY = "test-hermes"

    PUBLISH_RATE_LIMIT = int(from_env("MESSAGE RATE LIMIT", "40"))
    CALL_TIMES = []

    NEXMO_PUBLIC_KEY = ''
    NEXMO_PRIVATE_KEY = ''

    ERROR_REPORTING = ['error-reporting']
    NOTIFY_DEV = ['notify-dev']


class Production(Config):
    PRODUCTION = True
    DB_URL = from_env("DB_URL", "https://dynamodb.eu-west-1.amazonaws.com")


class Development(Config):
    DEBUG = True
    TESTING = True


class Testing(Config):
    TESTING = True
    API_KEY = ""
    SUBSCRIBERS = 'test_hermes_subscribers'
    SUBSCRIPTIONS = 'test_hermes_subscriptions'
    LOG = 'test_hermes_log'
    DB_URL = "https://dynamodb.eu-west-1.amazonaws.com"

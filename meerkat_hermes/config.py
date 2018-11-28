"""
config.py

Configuration and settings.
Kept inside the packages code so it can be easily imported within the package.
"""
import os


class Config(object):
    DEBUG = False
    TESTING = False
    PRODUCTION = False

    SUBSCRIBERS = 'hermes_subscribers'
    SUBSCRIPTIONS = 'hermes_subscriptions'
    LOG = 'hermes_log'

    DB_URL = os.environ.get("DB_URL", "http://dynamodb:8000")
    ROOT_URL = os.environ.get("MEERKAT_HERMES_ROOT", "/hermes")

    SENTRY_DNS = os.environ.get('SENTRY_DNS', '')

    SENDER = 'Notifications <notifications@emro.info>'
    CHARSET = 'UTF-8'
    FROM = 'Meerkat'

    PUBLISH_RATE_LIMIT = int(os.environ.get("MESSAGE RATE LIMIT", "75"))
    CALL_TIMES = []

    NEXMO_PUBLIC_KEY = ''
    NEXMO_PRIVATE_KEY = ''

    ERROR_REPORTING = ['error-reporting']
    NOTIFY_DEV = ['notify-dev']

    GCM_API_URL = "https://gcm-http.googleapis.com/gcm/send"
    GCM_AUTHENTICATION_KEY = ''
    GCM_ALLOWED_TOPICS = ['/topics/demo']
    GCM_MOCK_RESPONSE_ONLY = 1

    AUTH = {
        '/notify': [['slack'], ['meerkat']],
        'default': [['hermes'], ['meerkat']]
    }
    LOGGING_LEVEL = os.environ.get('LOGGING_LEVEL', 'INFO')
    LOGGING_FORMAT = '%(levelname)s - %(message)s'


class Production(Config):
    PRODUCTION = True
    LOGGING_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    DB_URL = os.environ.get(
        "DB_URL",
        "https://dynamodb.eu-west-1.amazonaws.com"
    )
    GCM_MOCK_RESPONSE_ONLY = 0
    GCM_ALLOWED_TOPICS = [
        '/topics/demo',
        '/topics/jordan',
        '/topics/madagascar',
        '/topics/somalia',
        '/topics/somaliland',
        '/topics/puntland'
    ]


class Development(Config):
    DEBUG = True
    TESTING = True


class Testing(Config):
    TESTING = True
    AUTH = {'default': [[], []]}
    SUBSCRIBERS = 'test_hermes_subscribers'
    SUBSCRIPTIONS = 'test_hermes_subscriptions'
    LOG = 'test_hermes_log'
    DB_URL = "https://dynamodb.eu-west-1.amazonaws.com"
    GCM_MOCK_RESPONSE_ONLY = 0

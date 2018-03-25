"""
config.py

Configuration and settings.
Kept inside the packages code so it can be easily imported within the package.
"""
from psycopg2 import sql
import os


class Config(object):
    DEBUG = False
    TESTING = False
    PRODUCTION = False

    SUBSCRIBERS = 'hermes_subscribers'
    LOG = 'hermes_log'

    DB_URL = os.environ.get("DB_URL", "http://dynamodb:8000")
    ROOT_URL = os.environ.get("MEERKAT_HERMES_ROOT", "/hermes")

    SENTRY_DNS = os.environ.get('SENTRY_DNS', '')

    SENDER = 'Notifications <notifications@emro.info>'
    CHARSET = 'UTF-8'

    PUBLISH_RATE_LIMIT = int(os.environ.get("MESSAGE RATE LIMIT", "40"))
    CALL_TIMES = []

    NEXMO_PUBLIC_KEY = ''
    NEXMO_PRIVATE_KEY = ''
    FROM = os.environ.get('MEERKAT_SMS_FROM', 'Meerkat')
    SMS_BACKEND = os.environ.get("MEERKAT_SMS_BACKEND", "SNS")
    ARABIA_USERNAME = os.environ.get("MEERKAT_ARABIA_USERNAME", "")
    ARABIA_PASSWORD = os.environ.get("MEERKAT_ARABIA_PASSWORD", "")

    ERROR_REPORTING = ['error-reporting']
    NOTIFY_DEV = ['notify-dev']

    EXCHANGE_EMAIL = os.environ.get("MEERKAT_EXCHANGE_EMAIL", "")
    EXCHANGE_SERVER = os.environ.get("MEERKAT_EXCHANGE_SERVER", "")
    EXCHANGE_USERNAME = os.environ.get("MEERKAT_EXCHANGE_USERNAME", "")
    EXCHANGE_PASSWORD = os.environ.get("MEERKAT_EXCHANGE_PASSWORD", "")

    EMAIL_BACKEND = os.environ.get("MEERKAT_EMAIL_BACKEND", "SES")
    SMTP_SERVER_ADDRESS = os.environ.get("MEERKAT_SMTP_SERVER_ADDRESS", "")

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

    # DB Adapters from meerkat libs enable us to use different dbs.
    POSTGRESQL_DSN = os.environ.get(
        "MEERKAT_POSTGRESQL_DSN",
        "host='db' dbname='meerkat_auth' user='postgres'"
    )
    POSTGRESQL_ROOT_DSN = os.environ.get(
        "MEERKAT_POSTGRESQL_DSN",
        "host='db' dbname='postgres' user='postgres'"
    )
    DYNAMODB_URL = os.environ.get("DB_URL", "http://dynamodb:8000")
    DB_ADAPTER = os.environ.get("MEERKAT_DB_ADAPTER", "DynamoDBAdapter")
    DB_ADAPTER_CONFIGS = {
        "DynamoDBAdapter": {
            'db_url': DYNAMODB_URL,
            "structure": {
                SUBSCRIBERS: {
                    "TableName": SUBSCRIBERS,
                    "AttributeDefinitions": [
                        {'AttributeName': 'id', 'AttributeType': 'S'},
                        {'AttributeName': 'email', 'AttributeType': 'S'}
                    ],
                    "KeySchema": [{'AttributeName': 'id', 'KeyType': 'HASH'}],
                    "ProvisionedThroughput": {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    },
                    "GlobalSecondaryIndexes": [{
                        'IndexName': 'email-index',
                        'KeySchema': [{
                            'AttributeName': 'email',
                            'KeyType': 'HASH'
                        }],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 1,
                            'WriteCapacityUnits': 1
                        }
                    }],
                },
                LOG: {
                    "TableName": LOG,
                    "AttributeDefinitions": [
                        {'AttributeName': 'id', 'AttributeType': 'S'},
                        {'AttributeName': 'message', 'AttributeType': 'S'}
                    ],
                    "KeySchema": [{'AttributeName': 'id', 'KeyType': 'HASH'}],
                    "ProvisionedThroughput": {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    },
                    "GlobalSecondaryIndexes": [{
                        'IndexName': 'message-index',
                        'KeySchema': [{
                            'AttributeName': 'message',
                            'KeyType': 'HASH'
                        }],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {
                            'ReadCapacityUnits': 1,
                            'WriteCapacityUnits': 1
                        }
                    }],
                }
            }
        },
        'PostgreSQLAdapter': {
            'connection_dsn': POSTGRESQL_DSN,
            'root_connection_dsn': POSTGRESQL_ROOT_DSN,
            'structure': {
                SUBSCRIBERS: [
                    ("id", sql.SQL("id VARCHAR(50) PRIMARY KEY")),
                    ("data",  sql.SQL("data JSONB"))
                ],
                LOG: [
                    ("id", sql.SQL("id VARCHAR(50) PRIMARY KEY")),
                    ("data", sql.SQL("data JSONB"))
                ]
            }
        }
    }


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

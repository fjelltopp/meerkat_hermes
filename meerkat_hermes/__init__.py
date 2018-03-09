"""
meerkat_hermes.py

Root Flask app for the Meerkat Hermes messaging module.
"""
from flask import Flask, request
from flask_restful import Api
from raven.contrib.flask import Sentry
from functools import wraps
from meerkat_libs.auth_client import auth
from meerkat_libs import db_adapters
import boto3
import logging
import os

# Create the Flask app
app = Flask(__name__)
config_object = os.getenv('CONFIG_OBJECT', 'meerkat_hermes.config.Development')
app.config.from_object(config_object)

# Confgure the logging
logger = logging.getLogger("meerkat_hermes")
if not logger.handlers:
    log_format = app.config['LOGGING_FORMAT']
    handler = logging.StreamHandler()
    formatter = logging.Formatter(log_format)
    handler.setFormatter(formatter)
    level_name = app.config["LOGGING_LEVEL"]
    level = logging.getLevelName(level_name)
    logger.setLevel(level)
    logger.addHandler(handler)
logger.info('App loaded with {} config object.'.format(config_object))


app.config.from_envvar('MEERKAT_HERMES_SETTINGS', silent=True)
api = Api(app)


# The DB is interfaced through an adapter determined by configs.
DBAdapter = getattr(db_adapters, app.config['DB_ADAPTER'])
db_configs = app.config['DB_ADAPTER_CONFIGS'][app.config['DB_ADAPTER']]
db = DBAdapter(**db_configs)

# Set up sentry error monitoring
if app.config["SENTRY_DNS"]:
    sentry = Sentry(app, dsn=app.config["SENTRY_DNS"])
else:
    sentry = None


# A decorator used to wrap up the authroisation process.
# This appears to be simplest way of putting access configs in app config.
def authorise(f):
    """
    @param f: flask function
    @return: decorator, return the wrapped function or abort json object.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
            # Load the authentication rule from configs,
            # based on the request url_rule.
            auth_rule = app.config['AUTH'].get(
                str(request.path),
                app.config['AUTH'].get(
                    str(request.url_rule),
                    app.config['AUTH'].get(
                        'default',
                        [['BROKEN'], ['']]
                    )
                )
            )
            logger.info("{} requires access: {}".format(
                request.path,
                auth_rule
            ))
            auth.check_auth(*auth_rule)
            return f(*args, **kwargs)
    return decorated


# Import the API resources
# Import them after creating the app, because they depend upon the app.
from meerkat_hermes.resources.subscribe import Subscribe
from meerkat_hermes.resources.email import Email
from meerkat_hermes.resources.sms import Sms
from meerkat_hermes.resources.gcm import Gcm
from meerkat_hermes.resources.publish import Publish, Error, Notify
from meerkat_hermes.resources.log import Log
from meerkat_hermes.resources.verify import Verify
from meerkat_hermes.resources.unsubscribe import Unsubscribe

# Add the API  resources.
api.add_resource(Subscribe, "/subscribe", "/subscribe/<string:subscriber_id>")
api.add_resource(Email, "/email")
api.add_resource(Sms, "/sms")
api.add_resource(Gcm, "/gcm")
api.add_resource(Publish, "/publish")
api.add_resource(Error, "/error")
api.add_resource(Notify, "/notify")
api.add_resource(Log, "/log/<string:log_id>")
api.add_resource(Verify, "/verify", "/verify/<string:subscriber_id>")
api.add_resource(Unsubscribe, "/unsubscribe/<string:subscriber_id>")


# display something at /
@app.route('/')
def hello_world():
    """
    Display something at /.
    This method loads a dynamodb table and displays its creation date.
    """
    logging.warning("Index called")
    db = boto3.resource(
        'dynamodb',
        endpoint_url=app.config['DB_URL'],
        region_name='eu-west-1'
    )
    table = db.Table(app.config['SUBSCRIBERS'])
    return table.creation_date_time.strftime('%d/%m/%Y')

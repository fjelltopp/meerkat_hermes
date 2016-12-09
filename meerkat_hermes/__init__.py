"""
meerkat_hermes.py

Root Flask app for the Meerkat Hermes messaging module.
"""
from flask import Flask
from flask_restful import Api
import boto3
import logging
import os

# Create the Flask app
app = Flask(__name__)
app.config.from_object(os.getenv('CONFIG_OBJECT', 'config.Development'))
try:
    app.config.from_envvar('MEERKAT_HERMES_SETTINGS')
except FileNotFoundError:
    logging.warning("No secret settings specified.")
api = Api(app)
logging.warning('App loaded')

# Import the API resources
# Import them after creating the app, because they depend upon the app.
from meerkat_hermes.resources.subscribe import Subscribe
from meerkat_hermes.resources.email import Email
from meerkat_hermes.resources.sms import Sms
from meerkat_hermes.resources.publish import Publish
from meerkat_hermes.resources.log import Log
from meerkat_hermes.resources.verify import Verify
from meerkat_hermes.resources.unsubscribe import Unsubscribe

# Add the API  resources.
api.add_resource(Subscribe, "/subscribe", "/subscribe/<string:subscriber_id>")
api.add_resource(Email, "/email")
api.add_resource(Sms, "/sms")
api.add_resource(Publish, "/publish")
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

"""
This resource provides a means for notifying developers about
errors in the system.
"""
from flask_restful import Resource, reqparse
import uuid
import boto3
import json
from flask import current_app, Response
import meerkat_hermes.util as util
from meerkat_hermes.authentication import require_api_key


class Error(Resource):

    # Require authentication
    decorators = [require_api_key]

    def __init__(self):
        # Load the database and tables, upon object creation.
        db = boto3.resource(
            'dynamodb',
            endpoint_url=current_app.config['DB_URL'],
            region_name='eu-west-1'
        )
        self.subscribers = db.Table(current_app.config['SUBSCRIBERS'])

    def put(self):
        """
        Notify the developers of an error in the system. Error notifications
        can be posted to slack and sent out via email and text.  These messages
        are not subject to the rate limiting that normal published messages are
        subject to.

        Args:
            message (str): Required. The e-mail message.\n
            subject (str): Optional. Defaults to "Meerkat Error".\n
            medium ([str]): Optional. A list of the following mediums: 'email',
                'sms', 'slack'. Defaults to ['slack','email'].\n
            sms-message (str): Optional. The sms version of the message.
                Defaults to the same as 'message'\n
            html-message (str): Optional. The html version of the message.
                Defaults to the same as 'message'\n
        Returns:
            The amazon SES response.
        """

        # Define the argument parser.
        parser = reqparse.RequestParser()
        parser.add_argument('message', required=True, type=str,
                            help='The message Id - must be unique.')
        parser.add_argument('subject', required=False,
                            type=str, help='The email subject')
        parser.add_argument('medium', required=False,
                            action='append', type=str,
                            help='The mediums by which to send the message.')
        parser.add_argument('sms-message', required=False, type=str,
                            help='If applicable, the seperate sms message')
        parser.add_argument('html-message', required=False, type=str,
                            help='If applicable, the message in html')
        args = parser.parse_args()

        # Set the default values for the non-required fields.
        if not args['subject']:
            args['subject'] = 'Meerkat Error'
        if not args['medium']:
            args['medium'] = ['email', 'slack']
        if not args['html-message']:
            args['html-message'] = args['message']
        if not args['sms-message']:
            args['sms-message'] = args['message']

        # Publish any messages to the hot-topic error-reporting.
        args['topics'] = current_app.config['ERROR_REPORTING']
        util.publish(args)

"""
This resource provides a simple means of sending a given e-mail message to
given e-mail addresses.
"""
from flask_restful import Resource, reqparse
from meerkat_hermes import authorise
from flask import Response
import meerkat_hermes.util as util
import json
import uuid


class Sms(Resource):

    decorators = [authorise]

    def put(self):
        """
        Send an sms message with Nexmo.
        First parse the given arguments to check it is a valid sms.

        Arguments are passed in the request data.

        Args:
            sms (str): The destination phone number.\n
            message (str): The sms message.

        Returns:
            The Nexmo response.
        """

        # Define an argument parser for creating a valid email message.
        parser = reqparse.RequestParser()
        parser.add_argument('sms', required=True, type=str,
                            help='The destination phone number')
        parser.add_argument('message', required=True,
                            type=str, help='The message to be sent')

        args = parser.parse_args()
        response = util.send_sms(
            args['sms'],
            args['message']
        )
        response = {} if not response else response

        # Log the message
        message_id = 'G' + uuid.uuid4().hex
        util.log_message(message_id, {
            'destination': [args['sms']],
            'medium': ['sms'],
            'time': util.get_date(),
            'message': args['message']
        })
        response['log_id'] = message_id

        return Response(json.dumps(response),
                        status=200,
                        mimetype='application/json')

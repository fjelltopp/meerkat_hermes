"""
This resource provides a simple means of sending a given e-mail message to
given e-mail addresses.
"""
from flask_restful import Resource, reqparse
import uuid
import boto3
import json
from flask import current_app, Response
import meerkat_hermes.util as util
from meerkat_hermes.authentication import require_api_key

class Gcm(Resource):

	# Require authentication
    decorators = [require_api_key]

    def put(self):
        """
        Send an GCM message
        First parse the given arguments to check it is a valid GCM message.

        Arguments are passed in the request data.

        Args:
            message (str): Required. The message payload.\n
            destination (str): Required. Destination subscriber id or topic for the message.\n

        Returns:
            The Google Cloud Messaging server response.
        """

        # Define an argument parser for creating a valid GCM message.
        parser = reqparse.RequestParser()
        parser.add_argument('message', required=True,
                            type=str, help='The message payload')
        parser.add_argument('destination', required=True, type=str,
                            help='The destination address')
        args = parser.parse_args()

        response = util.send_gcm(args['destination'], args['message'])
        if response.status_code == 200:
            response_dict = json.loads(response.text)
        else: 
            response_dict = {"message":response.text}

        message_id = 'G' + uuid.uuid4().hex

        util.log_message(message_id, {
            'destination': args['destination'],
            'medium': ['gcm'],
            'time': util.get_date(),
            'message': args['message']
        })

        response_dict['log_id'] = message_id

        return Response(json.dumps(response_dict),
                        status=response.status_code,
                        mimetype='application/json')

    def get(self):
    	return "Meerkat Google Cloud Messaging service"

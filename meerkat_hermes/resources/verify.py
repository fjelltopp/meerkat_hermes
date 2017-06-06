"""
If the subscriber hasn't been verified, their subscriptions to different topics
will not have been  created. This resource provides a generic means forcreating
and storing verify codes (one at a time) that can be used to verify any
communication medium. It is also used after a subscriber's details have been
verified, to make their subscriptions active.
"""
import boto3
import json
from flask_restful import Resource, reqparse
import meerkat_hermes.util as util
from flask import current_app, Response
from boto3.dynamodb.conditions import Key
from meerkat_hermes.authentication import require_api_key


class Verify(Resource):

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
        self.subscriptions = db.Table(current_app.config['SUBSCRIPTIONS'])

    def put(self):
        """
        Puts a new verify code into the verify attribute. This can then be
        checked using the post method and provides a generic means of verifying
        contact details for any communication medium.

        Arguments are passed in the request data.

        Args:
             subscriber_id (str): Required. The ID for the subscriber who has
                                  been verified.
             code (str): Required. The new code to be stored with the
                         subscriber.
        Returns:
             The amazon dynamodb response.
        """

        # Define an argument parser for creating a valid email message.
        parser = reqparse.RequestParser()
        parser.add_argument('code', required=True, type=str,
                            help='The new verify code')
        parser.add_argument('subscriber_id', required=True,
                            type=str, help='The subscriber\'s id')
        args = parser.parse_args()

        # Update the subscriber's verified field with the new verify code.
        response = self.subscribers.update_item(
            Key={
                'id': args['subscriber_id']
            },
            AttributeUpdates={
                'code': {
                    'Value': args['code']
                }
            }
        )

        return Response(json.dumps(response),
                        status=response['ResponseMetadata']['HTTPStatusCode'],
                        mimetype='application/json')

    def post(self):
        """
        Given a verify code, this method returns a boolean saying whether the
        given code matches the stored code.

        Arguments are passed in the request data.

        Post args:
             subscriber_id (str): Required. The ID for the subscriber who has
                                  been verified.
             code (str): Required. The code to be checked.
        Returns:
             A json blob with one boolean attribute "matched" saying whether
             the codes have matched. e.g. {"matched": true}
        """

        # Define an argument parser for creating a valid email message.
        parser = reqparse.RequestParser()
        parser.add_argument('code', required=True, type=str,
                            help='The code to be checked')
        parser.add_argument('subscriber_id', required=True,
                            type=str, help='The subscriber\'s id')
        args = parser.parse_args()

        # Get the stored verify code.
        response = self.subscribers.get_item(
            Key={
                'id': args['subscriber_id']
            },
            AttributesToGet=[
                'code'
            ]
        )

        if 'code' in response['Item']:
            message = {'matched': False}
            if response['Item']['code'] == args['code']:
                message['matched'] = True
            return Response(json.dumps(message),
                            status=response['ResponseMetadata'][
                                'HTTPStatusCode'],
                            mimetype='application/json')
        else:
            return Response(
                json.dumps({
                    'message': '400 Bad Request: Verification code not set'
                }),
                status=400,
                mimetype='application/json'
            )

    def get(self, subscriber_id):
        """
        Creates the subscriptions and sets the subscriber's "verified"
        attribute to True.

        Args:
             subscriber_id (str): The ID for the subscriber who has been
                                  verified.

        Returns:
             A json object with attribute "message" informing whether the
             verificaiton was successful e.g. {"message":"Subscriber verified"}
        """

        # Check subscriberID doesn't exist in subscriptions already
        exists = self.subscriptions.query(
            IndexName='subscriberID-index',
            KeyConditionExpression=Key('subscriberID').eq(subscriber_id)
        )

        # Get subscriber details.
        subscriber = self.subscribers.get_item(
            Key={
                'id': subscriber_id
            }
        )

        if not (exists['Items'] or subscriber['Item']['verified']):

            topics = subscriber['Item']['topics']

            # TODO: No longer create subscriptions.
            # Create the subscriptions
            # util.create_subscriptions(subscriber_id, topics)

            # Update the verified field and delete the code attribute.
            self.subscribers.update_item(
                Key={
                    'id': subscriber_id
                },
                AttributeUpdates={
                    'verified': {
                        'Value': True
                    },
                    'code': {
                        'Action': 'DELETE'
                    }
                }
            )

            return Response(
                json.dumps({"message": "Subscriber verified"}),
                status=200,
                mimetype='application/json'
            )

        else:
            return Response(
                json.dumps({
                    "message": "400 Bad Request: Subscriber already verified."
                }),
                status=400,
                mimetype='application/json'
            )

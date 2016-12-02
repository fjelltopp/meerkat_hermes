"""
This resource enables you to publish a message using given mediums to
subscribers with subscriptions to given topics. It is expected to hbe the
primary function of meerkat hermes.
"""

import boto3
import json
import logging
import meerkat_hermes.util as util
from flask_restful import Resource, reqparse
from flask import current_app, Response
from boto3.dynamodb.conditions import Key
from meerkat_hermes.authentication import require_api_key


# This Emailer resource has just one method, which sends a given email message.
class Publish(Resource):

    # Require authentication
    decorators = [require_api_key]

    def __init__(self):
        # Load the database
        db = boto3.resource(
            'dynamodb',
            endpoint_url=current_app.config['DB_URL'],
            region_name='eu-west-1'
        )
        self.subscribers = db.Table(current_app.config['SUBSCRIBERS'])
        self.subscriptions = db.Table(current_app.config['SUBSCRIPTIONS'])

    def put(self):
        """
        Publish a message to a given topic set. All subscribers with
        subscriptions to any of those topics are to receive the message. First
        parse the given arguments to check it is a valid email.

        Arguments are passed in the request data.

        Args:
            id (str): Required. If another message with the same ID has been
                      logged, this one won't send. Returns a 400 Bad Request
                      error if this is the case.\n
            message (str): Required. The message.\n
            topics ([str]): Required. The topics the message fits into
                            (determines destination address/es). Accepts array
                            of multiple topics.\n
            medium ([str]): The medium by which to publish the message
                            ('email', 'sms', etc...) Defaults to email. Accepts
                            array of multiple mediums.\n
            sms-message (str): The sms version of the message. Defaults to the
                               same as 'message'\n
            html-message (str): The html version of the message. Defaults to
                                the same as 'message'\n
            subject (str): The e-mail subject. Defaults to "".\n
            from (str): The address from which to send the message. \n
                        Deafults to an emro address stored in the config.

        Returns:
            An array of amazon SES and nexmo responses for each message sent.
        """
        # Define an argument parser for creating a valid email message.
        parser = reqparse.RequestParser()
        parser.add_argument('id', required=True, type=str,
                            help='The message Id - must be unique.')
        parser.add_argument('message', required=True,
                            type=str, help='The message to be sent')
        parser.add_argument('topics', required=True, action='append', type=str,
                            help='The topics to publish to.')
        parser.add_argument('medium', required=False,
                            action='append', type=str,
                            help='The mediums by which to send the message.')
        parser.add_argument('html-message', required=False, type=str,
                            help='If applicable, the message in html')
        parser.add_argument('sms-message', required=False, type=str,
                            help='If applicable, the seperate sms message')
        parser.add_argument('subject', required=False,
                            type=str, help='The email subject')
        parser.add_argument('from', required=False, type=str,
                            help='The address from which to send the message')
        args = parser.parse_args()

        logging.warning(current_app.config['CALL_TIMES'])

        # Check whether the rate limit has been exceeded.
        if util.limit_exceeded():
            # Log the issue.
            logging.warning("ERROR: Rate limit exceeded.\n{}".format(
                current_app.config['CALL_TIMES']
            ))
            # If limit exceeded, send 503 Service Unavailable error.
            message = {
                "message": ("503 Service Unavailable: too many requests " +
                            "to publish in the past hour. Try again later.")
            }
            return Response(json.dumps(message),
                            status=503,
                            mimetype='application/json')

        # Check that the message hasn't already been sent.
        if not util.id_valid(args['id']):
            # If the message ID exists, return with a 400 bad request response.
            message = {
                "message": ("400 Bad Request: id " + args['id'] +
                            " already exists")
            }
            return Response(json.dumps(message),
                            status=400,
                            mimetype='application/json')

        # Assuming everything is fine publish the message.
        # Set the default values for the non-required fields.
        if not args['medium']:
            args['medium'] = ['email']
        if not args['html-message']:
            args['html-message'] = args['message']
        if not args['sms-message']:
            args['sms-message'] = args['message']
        if not args['from']:
            args['from'] = current_app.config['SENDER']

        # Collect the subscriber IDs for all subscriptions to the given
        # topics.
        subscribers = []

        for topic in args['topics']:
            query_response = self.subscriptions.query(
                IndexName='topicID-index',
                KeyConditionExpression=Key('topicID').eq(topic)
            )
            for item in query_response['Items']:

                subscribers.append(item['subscriberID'])

        # Record details about the sent messages.
        responses = []
        destinations = []

        # Send the messages to each subscriber.
        for subscriber_id in subscribers:
            # Get subscriber's details.
            subscriber = self.subscribers.get_item(
                Key={'id': subscriber_id}
            )

            # Subscriptions can get left in database without a subscriber.
            # This can happen when someone mannually edits the database.
            # If so, no subscriber will be returned above, so we delete
            # subscriber properly.
            if(subscriber['ResponseMetadata']['HTTPStatusCode'] == 200 and
               'Item' not in subscriber):

                util.delete_subscriber(subscriber_id)
                message = {
                    "message": "500 Internal Server Error: subscriberid " +
                               subscriber_id + " doesn't exist. The "
                               "subscriber has been deleted properly."
                }
                current_app.logger.warning(message["message"])
                responses.append(message)

            else:

                subscriber = subscriber['Item']

                # Create some variables to hold the mailmerged messages.
                message = args['message']
                sms_message = args['sms-message']
                html_message = args['html-message']

                # Enable mail merging on subscriber attributes.
                message = util.replace_keywords(message, subscriber)
                if args['sms-message']:
                    sms_message = util.replace_keywords(
                        sms_message, subscriber
                    )
                if args['html-message']:
                    html_message = util.replace_keywords(
                        html_message, subscriber
                    )

                # Assemble and send the messages for each medium.
                for medium in args['medium']:

                    if medium == 'email':
                        temp = util.send_email(
                            [subscriber['email']],
                            args['subject'],
                            message,
                            html_message,
                            sender=args['from']
                        )
                        temp['type'] = 'email'
                        temp['message'] = message
                        responses.append(temp)
                        destinations.append(subscriber['email'])

                    elif medium == 'sms' and 'sms' in subscriber:
                        temp = util.send_sms(
                            subscriber['sms'],
                            sms_message
                        )
                        temp['type'] = 'sms'
                        temp['message'] = sms_message
                        responses.append(temp)
                        destinations.append(subscriber['sms'])

        util.log_message(args['id'], {
            'destination': destinations,
            'medium': args['medium'],
            'time': util.get_date(),
            'message': args['message'],
            'topics': 'Published to: ' + str(args['topics'])
        })

        return Response(json.dumps(responses),
                        status=200,
                        mimetype='application/json')

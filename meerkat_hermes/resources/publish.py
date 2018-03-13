"""
This resource enables you to publish a message using given mediums to
subscribers with subscriptions to given topics. It is expected to be the
primary function of meerkat hermes.
"""
from flask_restful import Resource, reqparse
from flask import Response
from meerkat_hermes import authorise, logger, app
import meerkat_hermes.util as util
import json


class Publish(Resource):

    decorators = [authorise]

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

        # Log previous times the publish function has been called
        logger.debug(app.config['CALL_TIMES'])

        # Check whether the rate limit has been exceeded.
        if util.limit_exceeded():
            # Log the issue.
            logger.error("Rate limit exceeded.\n{}".format(
                app.config['CALL_TIMES']
            ))
            # If limit exceeded, send 503 Service Unavailable error.
            message = {
                "message": ("503 Service Unavailable: too many requests " +
                            "to publish in the past hour. Try again later.")
            }
            # Notify the developers of the error
            util.error({
                'subject': 'URGENT ERROR - Message Rate Limit Exceeded',
                'message': ('The hermes messaging rate limit has been '
                            'exceeded. There have been {} attempts to publish '
                            'in the last hour. '.format(
                                len(app.config['CALL_TIMES'])
                            )),
                'medium': ['slack', 'email', 'sms']
            })
            return Response(json.dumps(message),
                            status=503,
                            mimetype='application/json')

        # Check that the message hasn't already been sent.
        if not util.id_valid(args['id']):
            logger.warning(
                "Can't publish message. ID {} already exists.".format(
                    args['id']
                )
            )
            # If the message ID exists, return with a 400 bad request response.
            message = {
                "message": ("400 Bad Request: id " + args['id'] +
                            " already exists")
            }
            return Response(json.dumps(message),
                            status=400,
                            mimetype='application/json')

        # Set the default values for the non-required fields.
        if not args['medium']:
            args['medium'] = ['email']
        if not args['html-message']:
            args['html-message'] = args['message']
        if not args['sms-message']:
            args['sms-message'] = args['message']
        if not args['from']:
            args['from'] = app.config['SENDER']

        # Assuming everything is fine publish the message.
        responses = util.publish(args)

        # Return responses.
        return Response(json.dumps(responses),
                        status=200,
                        mimetype='application/json')


class Notify(Resource):

    decorators = [authorise]

    def get(self):
        """
        Notify the developers on slack of some change in the system. This is a
        GET endpoint that can be used by services like Read The Docs to update
        developers. All args are passed as GET args.  Note that the auth token
        can be included in the get args.

        Args:
            message (str): Required. The slack message.\n
            subject (str): Required. The message title.\n

        Returns:
            The amazon SES response.
        """

        # Define the argument parser.
        parser = reqparse.RequestParser()
        parser.add_argument('message', required=True, type=str,
                            help='The message string.')
        parser.add_argument('subject', required=False,
                            type=str, help='The message subject.')
        args = parser.parse_args()

        args['medium'] = ['slack']

        responses = util.notify(args)

        # Return responses.
        return Response(json.dumps(responses),
                        status=200,
                        mimetype='application/json')

    def put(self):
        """
        Notify the developers of some change in the system. Notifications
        are automatically sent to slack.  These messages are not subject to
        the rate limiting that normal published messages are subject to.

        Args:
            message (str): Required. The e-mail message.\n
            subject (str): Optional. Defaults to "Meerkat Notice".\n
            medium ([str]): Optional. A list of the following mediums: 'email',
                'sms', 'slack'. Defaults to ['slack'].\n
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

        responses = util.notify(args)

        # Return responses.
        return Response(json.dumps(responses),
                        status=200,
                        mimetype='application/json')


class Error(Resource):

    decorators = [authorise]

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

        responses = util.error(args)

        # Return responses.
        return Response(json.dumps(responses),
                        status=200,
                        mimetype='application/json')

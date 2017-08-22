from meerkat_hermes import app
from flask import Response
from datetime import datetime, timedelta
import uuid
import boto3
import urllib
import time
import json
import requests


def slack(channel, message, subject=''):
    """
    Sends a notification to meerkat slack server.  Channel is '#deploy' only if
    in live deployment, otherwise sent privately to the developer via slackbot.

    Args:
        channel (str): Required. The channel or username to which the message
        should be posted.
        message (str): Required. The message to post to slack.\n
        subject (str): Optional. Placed in bold and seperated by a pipe.

    return "sent"
    """

    # Assemble the message text string
    text = str(message)
    if subject:
        text = "*_{}_* | {}".format(subject, message)

    # Send the slack message
    message = {'text': text, 'channel': channel, 'username': 'Meerkat'}
    url = ('https://hooks.slack.com/services/T050E3XPP/'
           'B0G7UKUCA/EtXIFB3CRGyey2L7x5WbT32B')
    headers = {'Content-Type': 'application/json'}
    r = requests.post(url, data=json.dumps(message), headers=headers)

    # Return the slack response
    return r


def subscribe(first_name, last_name, email,
              country, topics, sms="", slack="", verified=False):
    """
    Subscribes a user.  Factored out of the resources so it can be called
    easily from python code.

    Args:
        first_name (str): Required. The subscriber's first name.\n
        last_name (str): Required. The subscriber's last name.\n
        email (str): Required. The subscriber's email address.\n
        country (str): Required. The country that the subscriber has signed
                       up to.\n
        sms (str): The subscribers phone number for sms.\n
        slack (str): The slack username or channel.
        topics ([str]): Required. The ID's for the topics to which the
                        subscriber wishes to subscribe.\n
        verified (bool): Are their contact details verified? Defaults to
                         False.
    """

    # Assign the new subscriber a unique id.
    subscriber_id = uuid.uuid4().hex

    # Create the subscriber object.
    subscriber = {
        'id': subscriber_id,
        'first_name': first_name,
        'last_name': last_name,
        'country': country,
        'email': email,
        'topics': topics,
        'verified': False
    }

    if sms:
        subscriber['sms'] = sms
    if slack:
        subscriber['slack'] = slack
    if verified:
        subscriber['verified'] = verified

    # Write the subscriber to the database.
    db = boto3.resource(
        'dynamodb',
        endpoint_url=app.config['DB_URL'],
        region_name='eu-west-1'
    )
    subscribers = db.Table(app.config['SUBSCRIBERS'])
    response = subscribers.put_item(Item=subscriber)
    response['subscriber_id'] = subscriber_id

    return response


def send_email(destination, subject, message, html, sender):
    """
    Sends an email using Amazon SES.

    Args:
        destination ([str]): Required. The email address to send to.\n
        subject (str): Required. The email subject. \n
        message (str): Required. The message to be sent. \n
        html (str): The html version of the message to be sent.
                    Defaults to the same as 'message'. \n
        sender (str): The sender's address. Must be an AWS SES verified email
                      address. Defaults to the config file SENDER value.

    Returns:
        The Amazon SES response. If email fails, returns a response look-a-like
        object that contains the failiure error message.
    """

    client = boto3.client('ses', region_name='eu-west-1')

    if(not html):
        html = message.replace('\n', '<br />')

    try:
        response = client.send_email(
            Source=sender,
            Destination={
                'ToAddresses': destination
            },
            Message={
                'Subject': {
                    'Data': subject,
                    'Charset': app.config['CHARSET']
                },
                'Body': {
                    'Text': {
                        'Data': message,
                        'Charset': app.config['CHARSET']
                    },
                    'Html': {
                        'Data': html,
                        'Charset': app.config['CHARSET']
                    }
                }
            }
        )
        response['SesMessageId'] = response.pop('MessageId')
        response['Destination'] = destination
        return response

    except Exception as e:
        msg = "Failed to send email \"{}\" to: {}\n{}".format(
            subject,
            destination,
            e
        )
        app.logger.error(msg)
        return {'ResponseMetadata': {'error': msg, 'HTTPStatusCode': 400}}


def send_gcm(destination, message):
    """
    Sends a notification to a tablet running the Collect app using a GCM
    subscription id

    Args:
        destination ([str]): Required. The GCM subscriber ID or topic to send\n
        message (str): Required. The message to be sent. \n

    Returns:
        The Google Cloud Messaging server response.
    """
    headers = {"Content-Type": "application/json"}

    headers["Authorization"] = "key=" + app.config['GCM_AUTHENTICATION_KEY']

    payload = {"data": {"message": message}, "to": destination}

    response = requests.post(
        app.config['GCM_API_URL'],
        data=json.dumps(payload),
        headers=headers
    )

    return Response(
        response.text,
        status=response.status_code,
        mimetype='application/json'
    )


def log_message(messageID, details):
    """
    Logs that a message has been sent in the relavent dynamodb table.

    Args:
        messageID (str): Required. The unique message ID to be logged (Str)
                         Will fail if the messageID already exists.\n
        details (dict): Required. A dictionary containing any further details
                        you wish to store. Typically: destinations, message,
                        time and medium and optionally topics.

    Returns:
        The Amazon DynamoDB response.
    """
    db = boto3.resource(
        'dynamodb',
        endpoint_url=app.config['DB_URL'],
        region_name='eu-west-1'
    )
    table = db.Table(app.config['LOG'])

    details['id'] = messageID

    # If the paramaeters are too large, it can cause problems.
    try:
        response = table.put_item(Item=details)
    except Exception:
        details['message'] = 'Message too large to log.'
        response = table.put_item(Item=details)

    return response, 200


def limit_exceeded():
    """
    Each time the method is called, the time of calling is recorded.
    It then checks whether more than the allowed threshold number of calls
    has  been made in the past hour.

    Returns:
        True if more than the allowed threshold number of calls has been
        made. False otherwise.

    """
    app.config['CALL_TIMES'].append(datetime.now())
    while app.config['CALL_TIMES'][0] < datetime.now()-timedelta(hours=1):
            app.config['CALL_TIMES'].pop(0)
    return len(app.config['CALL_TIMES']) > app.config['PUBLISH_RATE_LIMIT']


def send_sms(destination, message):
    """
    Sends an sms message using Nexmo.

    Args:
        destination (str): Required. The sms number to send to.\n
        message (str): Required. The message to be sent.

    Returns:
        The Nexmo response.
    """
    params = {
        'api_key': app.config['NEXMO_PUBLIC_KEY'],
        'api_secret': app.config['NEXMO_PRIVATE_KEY'],
        'to': destination,
        'from': app.config['FROM'],
        'text': message
    }

    url = 'https://rest.nexmo.com/sms/json?' + urllib.parse.urlencode(params)
    response = urllib.request.urlopen(url)
    response = json.loads(response.read().decode('UTF-8'))
    return response


def get_date():
    """
    Function to retreive a current timestamp.

       Returns:
           The current date and time in Y:M:DTH:M:S format.
    """
    return datetime.fromtimestamp(time.time()).strftime('%Y:%m:%dT%H:%M:%S')


def id_valid(messageID):
    """
    Checks whether or not the given messageID has already been logged.

    Returns:
        bool - True for a valid message ID, False for one that has already
               been logged.
    """
    db = boto3.resource(
        'dynamodb',
        endpoint_url=app.config['DB_URL'],
        region_name='eu-west-1'
    )
    table = db.Table(app.config['LOG'])
    response = table.get_item(
        Key={
            'id': messageID
        }
    )

    if 'Item' in response:
        return False
    else:
        return True


def replace_keywords(message, subscriber):

    for key in subscriber:
        placeholder = "<<" + key + ">>"
        replace = str(subscriber[key])
        # If it's a list, e.g. topics, then it's a little more complicated.
        if isinstance(subscriber[key], list):
            replace = ""
            for i in range(len(subscriber[key])):
                replace += subscriber[key][i]
                if i < len(subscriber[key]) - 2:
                    replace += ', '
                elif i == len(subscriber[key]) - 2:
                    replace += ' and '
        message = message.replace(placeholder, replace)
    return message


def delete_subscriber(subscriber_id):
    """
    Delete a subscriber from the database. At the moment, if a user wishes to
    change information, they need to delete themselves and then re-add
    themselves with the new information.

    Args:
         subscriber_id (str)
    Returns:
         The amazon dynamodb response.
    """
    db = boto3.resource(
        'dynamodb',
        endpoint_url=app.config['DB_URL'],
        region_name='eu-west-1'
    )
    subscribers = db.Table(app.config['SUBSCRIBERS'])

    subscribers_response = subscribers.delete_item(
        Key={
            'id': subscriber_id
        }
    )

    status = 200
    response = ("<html><body><H2>You have been "
                "successfully unsubscribed.</H2></body</html>")
    mimetype = 'text/html'

    if not subscribers_response['ResponseMetadata']['HTTPStatusCode'] == 200:
        status = 500
        response = ("{'message':'500 Internal Server "
                    "Error: Unable to complete deletion.'}")
        mimetype = 'application/json'

    return Response(response,
                    status=status,
                    mimetype=mimetype)


def publish(args):
    """
    Publishes a message to a given topic set. All subscribers with
    subscriptions to any of those topics are to receive the message.

    Arguments are passed in the request data.

    Args:
        args (dictionary): Should contiain the following key/value pairs:\n
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

    # Set the default values for the non-required fields.
    if not args.get('medium', ''):
        args['medium'] = ['email']
    if not args.get('html-message', ''):
        args['html-message'] = args['message']
    if not args.get('sms-message', ''):
        args['sms-message'] = args['message']
    if not args.get('from', ''):
        args['from'] = app.config['SENDER']

    # Load the database.
    db = boto3.resource(
        'dynamodb',
        endpoint_url=app.config['DB_URL'],
        region_name='eu-west-1'
    )
    subscribers_table = db.Table(app.config['SUBSCRIBERS'])

    # Identify those subscribed to the given topics.
    subscribers = {}
    kwargs = {}
    # Load data separately for each country - Scan can't perform OR on CONTAINS
    for topic in args['topics']:
        kwargs["ScanFilter"] = {
            'topics': {
                'AttributeValueList': [topic],
                'ComparisonOperator': 'CONTAINS'
            },
            'verified': {
                'AttributeValueList': [True],
                'ComparisonOperator': 'EQ'
            }
        }
        # Get and combine the users together in a no-duplications dict.
        for subscriber in subscribers_table.scan(**kwargs).get("Items", []):
            subscribers[subscriber["id"]] = subscriber

    print('\nSUBSCRIBERS: ' + str(subscribers))

    # Record details about the sent messages.
    responses = []
    destinations = []

    # Send the messages to each subscriber.
    for subscriber_id, subscriber in subscribers.items():

        # Create some variables to hold the mailmerged messages.
        message = args['message']
        sms_message = args['sms-message']
        html_message = args['html-message']

        # Enable mail merging on subscriber attributes.
        message = replace_keywords(message, subscriber)
        if args['sms-message']:
            sms_message = replace_keywords(
                sms_message, subscriber
            )
        if args['html-message']:
            html_message = replace_keywords(
                html_message, subscriber
            )

        # Assemble and send the messages for each medium.
        if 'email' in args['medium']:
            temp = send_email(
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

        if 'sms' in args['medium'] and 'sms' in subscriber:
            temp = send_sms(
                subscriber['sms'],
                sms_message
            )
            temp['type'] = 'sms'
            temp['message'] = sms_message
            responses.append(temp)
            destinations.append(subscriber['sms'])

        if 'slack' in args['medium'] and 'slack' in subscriber:
            temp = slack(
                subscriber['slack'],
                message,
                args['subject']
            )
            request_status = {
                'message': message,
                'type': 'slack',
                'code': temp.status_code
            }
            responses.append(request_status)
            destinations.append(subscriber['slack'])

    # Log the message
    log_message(args['id'], {
        'destination': destinations,
        'medium': args['medium'],
        'time': get_date(),
        'message': args['message'],
        'topics': 'Published to: ' + str(args['topics'])
    })

    return responses


def error(args):
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
    # Set the default values for the non-required fields.
    if not args.get('subject', ''):
        args['subject'] = 'Meerkat Error'
    if not args.get('medium', ''):
        args['medium'] = ['email', 'slack']
    if not args.get('html-message', ''):
        args['html-message'] = args['message']
    if not args.get('sms-message', ''):
        args['sms-message'] = args['message']

    # Publish any messages to the hot-topic error-reporting.
    args['topics'] = app.config['ERROR_REPORTING']
    args['id'] = 'ERROR-'+str(datetime.now().isoformat())

    # Publish!
    return publish(args)


def notify(args):
    """
    Notify the developers of some change in the system. Notifications
    are automatically sent to slack.  These messages are not subject to
    the rate limiting that normal published messages are subject to.

    Args:
        message (str): Required. The e-mail message.\n
        subject (str): Optional. Defaults to "Meerkat Notification".\n
        medium ([str]): Optional. A list of the following mediums: 'email',
            'sms', 'slack'. Defaults to ['slack'].\n
        sms-message (str): Optional. The sms version of the message.
            Defaults to the same as 'message'\n
        html-message (str): Optional. The html version of the message.
            Defaults to the same as 'message'\n
    Returns:
        The amazon SES response.
    """
    # Set the default values for the non-required fields.
    if not args.get('subject', ''):
        args['subject'] = 'Meerkat Notification'
    if not args.get('medium', ''):
        args['medium'] = ['slack']
    if not args.get('html-message', ''):
        args['html-message'] = args['message']
    if not args.get('sms-message', ''):
        args['sms-message'] = args['message']

    # Publish any messages to the hot-topic notices.
    args['topics'] = app.config['NOTIFY_DEV']
    args['id'] = 'NOTICE-'+str(datetime.now().isoformat())

    # Publish!
    return publish(args)

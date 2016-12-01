import meerkat_hermes
from meerkat_hermes import app
from flask import Response
from boto3.dynamodb.conditions import Key
from datetime import datetime
import uuid
import boto3
import urllib
import time
import json


def subscribe(first_name, last_name, email,
              country, topics, sms="", verified=False):
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
    if verified:
        subscriber['verified'] = verified

    # Write the subscriber to the database.
    db = boto3.resource(
        'dynamodb',
        endpoint_url=app.config['DB_URL'],
        region_name='eu-west-1'
    )
    subscribers = db.Table(meerkat_hermes.app.config['SUBSCRIBERS'])
    response = subscribers.put_item(Item=subscriber)
    response['subscriber_id'] = subscriber_id

    # If the subscriber has already been verified, create the subscriptions.
    if subscriber['verified']:
        create_subscriptions(subscriber_id, topics)

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
        The Amazon SES response.
    """

    # Load the email client
    client = boto3.client('ses', region_name='eu-west-1')

    if(not html):
        html = message.replace('\n', '<br />')

    response = client.send_email(
        Source=sender,
        Destination={
            'ToAddresses': destination
        },
        Message={
            'Subject': {
                'Data': subject,
                'Charset': meerkat_hermes.app.config['CHARSET']
            },
            'Body': {
                'Text': {
                    'Data': message,
                    'Charset': meerkat_hermes.app.config['CHARSET']
                },
                'Html': {
                    'Data': html,
                    'Charset': meerkat_hermes.app.config['CHARSET']
                }
            }
        }
    )

    response['SesMessageId'] = response.pop('MessageId')
    response['Destination'] = destination

    return response


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
        endpoint_url=meerkat_hermes.app.config['DB_URL'],
        region_name='eu-west-1'
    )
    table = db.Table(meerkat_hermes.app.config['LOG'])

    details['id'] = messageID
    response = table.put_item(Item=details)

    return response, 200


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
        'api_key': meerkat_hermes.app.config['NEXMO_PUBLIC_KEY'],
        'api_secret': meerkat_hermes.app.config['NEXMO_PRIVATE_KEY'],
        'to': destination,
        'from': meerkat_hermes.app.config['FROM'],
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
        endpoint_url=meerkat_hermes.app.config['DB_URL'],
        region_name='eu-west-1'
    )
    table = db.Table(meerkat_hermes.app.config['LOG'])
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


def create_subscriptions(subscriber_id, topics):
    db = boto3.resource(
        'dynamodb',
        endpoint_url=meerkat_hermes.app.config['DB_URL'],
        region_name='eu-west-1'
    )
    table = db.Table(meerkat_hermes.app.config['SUBSCRIPTIONS'])

    with table.batch_writer() as batch:
        for topic_id in topics:
            batch.put_item(
                Item={
                    'subscriptionID': uuid.uuid4().hex,
                    'topicID': topic_id,
                    'subscriberID': subscriber_id
                }
            )


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
        endpoint_url=meerkat_hermes.app.config['DB_URL'],
        region_name='eu-west-1'
    )
    subscribers = db.Table(meerkat_hermes.app.config['SUBSCRIBERS'])
    subscriptions = db.Table(meerkat_hermes.app.config['SUBSCRIPTIONS'])

    subscribers_response = subscribers.delete_item(
        Key={
            'id': subscriber_id
        }
    )

    # dynamoDB doesn't currently support deletions by secondary indexes
    # it may appear in the future.
    # Deleteing by subscriber index is therefore a two hop process.
    # (1) Query for the primary key values i.e.topicID (2) Using topicID's,
    # batch delete the records.
    # TODO: My understanding has changed, there is a better way of doing this.
    query_response = subscriptions.query(
        IndexName='subscriberID-index',
        KeyConditionExpression=Key('subscriberID').eq(subscriber_id)
    )

    with subscriptions.batch_writer() as batch:
        for record in query_response['Items']:
            batch.delete_item(
                Key={
                    'subscriptionID': record['subscriptionID']
                }
            )

    status = 200
    response = ("<html><body><H2>You have been "
                "successfully unsubscribed.</H2></body</html>")
    mimetype = 'text/html'

    if not subscribers_response['ResponseMetadata']['HTTPStatusCode'] == 200:
        if not query_response['ResponseMetadata']['HTTPStatusCode'] == 200:
            status = 500
            response = ("{'message':'500 Internal Server "
                        "Error: Unable to complete deletion.'}")
            mimetype = 'application/json'

    return Response(response,
                    status=status,
                    mimetype=mimetype)

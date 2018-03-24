from meerkat_hermes import app, logger
from flask import Response
from datetime import datetime, timedelta
from exchangelib import DELEGATE, Account, Credentials, HTMLBody
from exchangelib import Configuration, Message, Mailbox
from smtplib import SMTP
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import uuid
import boto3
import time
import json
import requests
import base64


def slack(channel, message, subject=''):
    """
    Sends a notification to meerkat slack server.  Channel is '#deploy' only if
    in live deployment, otherwise sent privately to the developer via slackbot.

    Args:
        channel (str): Required. The channel or username to which the message
        should be posted.
        message (str): Required. The message to post to slack.
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
        first_name (str): Required. The subscriber's first name.
        last_name (str): Required. The subscriber's last name.
        email (str): Required. The subscriber's email address.
        country (str): Required. The country that the subscriber has signed up to.
        sms (str): The subscribers phone number for sms.
        slack (str): The slack username or channel.
        topics ([str]): Required. The ID's for the topics to which the subscriber \
            wishes to subscribe.
        verified (bool): Are their contact details verified? Defaults to False.
    """

    # Assign the new subscriber a unique id.
    subscriber_id = uuid.uuid4().hex

    # Create the subscriber object.
    subscriber = {
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
    response = app.db.write(
        app.config['SUBSCRIBERS'],
        {'id': subscriber_id},
        subscriber
    )

    if not response:
        return {'subscriber_id': subscriber_id}
    else:
        return {**response, **{'subscriber_id': subscriber_id}}


def send_email(destination, subject, message, html, sender):
    """
    Sends and email using the configured email backend

    Args:
        destination ([str]): Required. The email address to send to.
        subject (str): Required. The email subject.
        message (str): Required. The message to be sent.
        html (str): The html version of the message to be sent. Defaults to \
            the same as 'message'.
        sender (str): The sender's address. Must be an AWS SES verified email \
            address. Defaults to the config file SENDER value.

    Returns:
        The email response. If email fails, returns a response look-a-like
        object that contains the failiure error message.
    """

    if app.config['EMAIL_BACKEND'] == "SES":
        result = send_email_ses(destination, subject, message, html, sender)
    elif app.config['EMAIL_BACKEND'] == "SMTP":
        result = send_email_smtp(destination, subject, message, html, sender)
    elif app.config['EMAIL_BACKEND'] == "EXCHANGE":
        result = send_email_exchange(destination, subject, message, html, sender)
    return result


def send_email_exchange(destination, subject, message, html, sender):
    """
    Sends an email using a Microsoft exchange server.

    Args:
        destination ([str]): Required. The email address to send to.
        subject (str): Required. The email subject.
        message (str): Required. The message to be sent.
        html (str): The html version of the message to be sent. Defaults to \
            the same as 'message'.
        sender (str): The sender's address. Must be an AWS SES verified email \
            address. Defaults to the config file SENDER value.

    Returns:
        Nothing on success.  If email fails, returns a response
        look-a-like object that contains the failiure error message.
    """

    try:
        credentials = Credentials(
            username=app.config['EXCHANGE_USERNAME'],
            password=app.config['EXCHANGE_PASSWORD'],
        )
        config = Configuration(
            server=app.config['EXCHANGE_SERVER'],
            credentials=credentials
        )
        account = Account(
            primary_smtp_address=app.config['EXCHANGE_EMAIL'],
            config=config,
            autodiscover=False,
            access_type=DELEGATE
        )
        recipients = [Mailbox(email_address=x) for x in destination]
        m = Message(
            account=account,
            folder=account.sent,
            subject=subject,
            text_body=message,
            body=HTMLBody(html),
            to_recipients=recipients
        )
        m.send_and_save()

    except Exception as e:
        msg = "Failed to send email \"{}\" to: {}{}".format(
            subject,
            destination,
            e
        )
        logger.error(msg)
        return {'ResponseMetadata': {'error': msg, 'HTTPStatusCode': 400}}


def send_email_smtp(destination, subject, message, html, sender):
    """
    Sends an email using an SMTP server.

    Args:
        destination ([str]): Required. The email address to send to.
        subject (str): Required. The email subject.
        message (str): Required. The message to be sent.
        html (str): The html version of the message to be sent. Defaults to \
            the same as 'message'.
        sender (str): The sender's address. Must be an AWS SES verified email \
            address. Defaults to the config file SENDER value.

    Returns:
        An Amazon SES like response. If email fails, returns a response look-a-like
        object that contains the failiure error message.
    """

    # Assemble a MIME multipart message with both plain text and html
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = destination
    plain_part = MIMEText(message, 'plain')
    html_part = MIMEText(html, 'html')
    msg.attach(plain_part)
    msg.attach(html_part)

    # Send email using SMTPlib
    try:
        with SMTP(host=app.config['SMTP_SERVER_ADDRESS']) as smtp:
            smtp.sendmail(sender, destination, msg.as_string())
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    except Exception as e:
        msg = "Failed to send email \"{}\" to: {}{}".format(
            subject,
            destination,
            e
        )
        logger.error(msg)
        return {'ResponseMetadata': {'error': msg, 'HTTPStatusCode': 400}}


def send_email_ses(destination, subject, message, html, sender):
    """
    Sends an email using Amazon SES.

    Args:
        destination ([str]): Required. The email address to send to.
        subject (str): Required. The email subject.
        message (str): Required. The message to be sent.
        html (str): The html version of the message to be sent. Defaults to \
            the same as 'message'.
        sender (str): The sender's address. Must be an AWS SES verified email \
            address. Defaults to the config file SENDER value.

    Returns:
        The Amazon SES response. If email fails, returns a response look-a-like
        object that contains the failiure error message.
    """

    client = boto3.client('ses', region_name='eu-west-1')

    if(not html):
        html = message.replace('', '<br />')

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
        msg = "Failed to send email \"{}\" to: {}{}".format(
            subject,
            destination,
            e
        )
        logger.error(msg)
        return {'ResponseMetadata': {'error': msg, 'HTTPStatusCode': 400}}


def send_gcm(destination, message):
    """
    Sends a notification to a tablet running the Collect app using a GCM
    subscription id

    Args:
        destination ([str]): Required. The GCM subscriber ID or topic to send
        message (str): Required. The message to be sent.

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
        messageID (str): Required. The unique message ID to be logged (Str) \
            Will fail if the messageID already exists.
        details (dict): Required. A dictionary containing any further details \
            you wish to store. Typically: destinations, message, time and \
            medium and optionally topics.

    Returns:
        The Amazon DynamoDB response.
    """
    details['id'] = messageID
    # If the paramaeters are too large, it can cause problems.
    try:
        response = app.db.write(app.config['LOG'], {'id': messageID}, details)
    except Exception:
        details['message'] = 'Message too large to log.'
        response = app.db.write(app.config['LOG'], {'id': messageID}, details)
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
    Sends an sms message using the configured back end.

    Args:
        destination (str): Required. The sms number to send to.
        message (str): Required. The message to be sent.

    Returns:
        The SMS API response.
    """
    if app.config['SMS_BACKEND'] == "SNS":
        result = send_sms_sns(destination, message)
    elif app.config['SMS_BACKEND'] == "ARABIA":
        result = send_sms_arabia(destination, message)
    return result


def send_sms_sns(destination, message):
    """
    Sends an sms message using AWS SNS.

    Args:
        destination (str): Required. The sms number to send to.
        message (str): Required. The message to be sent.

    Returns:
        The AWS response.
    """

    client = boto3.client('sns', region_name='eu-west-1')
    response = client.publish(
        PhoneNumber=destination,
        Message=message,
        MessageAttributes={
            'AWS.SNS.SMS.SenderID': {
                'DataType': 'String',
                'StringValue': app.config['FROM']
            }
        }
    )
    return response


def send_sms_arabia(destination, message):
    """
    Sends an sms message using the Arabia Cell SMS API.
    This function is primarily for jordan.

    Args:
        destination (str): Required. The sms number to send to.
        message (str): Required. The message to be sent.

    Returns:
        The SMS API response.
    """
    payload = {
        'mobile_number': destination,
        'msg': message,
        'from': app.config['FROM'],
        'tag': 3,
    }
    url = 'https://bulksms.arabiacell.net/index.php/api/send_sms/send'
    credentials = "{}:{}".format(
        app.config['ARABIA_USERNAME'],
        app.config['ARABIA_PASSWORD']
    ).encode('UTF-8')
    b64_credentials = base64.b64encode(credentials).decode('UTF-8')
    headers = {'Authorization': 'Basic {}'.format(b64_credentials)}
    response = requests.post(url, data=payload, headers=headers)
    return {'message': response.content.decode('UTF-8')}


def get_date():
    """
    Function to retreive a current timestamp.

    Returns:
        The current date and time as a string.
    """
    return datetime.fromtimestamp(time.time()).strftime('%Y:%m:%dT%H:%M:%S')


def id_valid(messageID):
    """
    Checks whether or not the given messageID has already been logged.

    Returns:
        True for a valid message ID, False for one that has already been logged.
    """
    response = app.db.read(app.config['LOG'], {'id': messageID})

    if response:
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
    try:
        app.db.delete(
            app.config['SUBSCRIBERS'],
            {'id': subscriber_id}
        )
        status = 200
        response = ("<html><body><H2>You have been "
                    "successfully unsubscribed.</H2></body</html>")
        mimetype = 'text/html'

    except Exception:
        status = 500
        response = ("{'message':'500 Internal Server "
                    "Exeption raised: Unable to complete deletion.'}")
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
        args (dictionary): Should contiain the following key/value pairs:
            id (str): Required. If another message with the same ID has been \
                logged, this one won't send. Returns a 400 Bad Request error \
                if this is the case.
            message (str): Required. The message.
            topics ([str]): Required. The topics the message fits into (determines \
                destination address/es). Accepts array of multiple topics.
            medium ([str]): The medium by which to publish the message ('email', \
                'sms', etc...) Defaults to email. Accepts array of multiple mediums.
            sms-message (str): The sms version of the message. Defaults to the \
                same as 'message'
            html-message (str): The html version of the message. Defaults to the \
                same as 'message'
            subject (str): The e-mail subject. Defaults to "".
            from (str): The address from which to send the message. Deafults to \
                an emro address stored in the config.

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

    # Get verfied accounts subscribed to the specified topics.
    subscribers = filter(lambda x: x['verified'], app.db.get_all(
        app.config['SUBSCRIBERS'],
        {'topics': args['topics']}
    ))
    print('\nSUBSCRIBERS: ' + str(subscribers))

    # Record details about the sent messages.
    responses = []
    destinations = []

    # Send the messages to each subscriber.
    for subscriber in subscribers:

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
        message (str): Required. The e-mail message.
        subject (str): Optional. Defaults to "Meerkat Error".
        medium ([str]): Optional. A list of the following mediums: 'email',
            'sms', 'slack'. Defaults to ['slack','email'].
        sms-message (str): Optional. The sms version of the message.
            Defaults to the same as 'message'
        html-message (str): Optional. The html version of the message.
            Defaults to the same as 'message'
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
        message (str): Required. The e-mail message.
        subject (str): Optional. Defaults to "Meerkat Notification".
        medium ([str]): Optional. A list of the following mediums: 'email',
            'sms', 'slack'. Defaults to ['slack'].
        sms-message (str): Optional. The sms version of the message.
            Defaults to the same as 'message'
        html-message (str): Optional. The html version of the message.
            Defaults to the same as 'message'
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

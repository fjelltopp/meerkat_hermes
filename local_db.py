#!/usr/local/bin/python3
"""
This is a utility script to help set up some accounts for testing and
development. It create a registered, manager and root account for every country
currently under active development. NOTE: the passwords for every account is
just 'password'.

Run:
    `local_db.py --clear` (To get rid of any existing db)
    `local_db.py --setup` (To setup the db tables)
    `local_db.py --populate` (To populate the tables with accounts & roles)
    `local_db.py --list` (To list the acounts in the db)

If no flag is provided (i.e. you just run `local_db.py`) it will perform all
steps in the above order.

You can run these commands inside the docker container if there are database
issues.
"""
from meerkat_hermes import app
from meerkat_hermes import util
import boto3
import os
import ast
import argparse

# PARSE ARGUMENTS
parser = argparse.ArgumentParser()
parser.add_argument(
    '--setup',
    help='Setup the local dynamodb development database.', action='store_true'
)
parser.add_argument(
    '--list',
    help='List data from the local dynamodb development database.',
    action='store_true'
)
parser.add_argument(
    '--clear',
    help='Clear the local dynamodb development database.',
    action='store_true'
)
parser.add_argument(
    '--populate',
    help='Populate the local dynamodb development database.',
    action='store_true'
)
args = parser.parse_args()
args_dict = vars(args)

# If no arguments are specified assume that we want to do everything.
if all(arg is False for arg in args_dict.values()):
    print("Re-starting the dev database.")
    for arg in args_dict:
        args_dict[arg] = True

# Clear the database
if args.clear:
    db = boto3.resource(
        'dynamodb',
        endpoint_url='http://dynamodb:8000',
        region_name='eu_west'
    )
    try:
        print('Cleaning the dev db.')
        response = db.Table(app.config['SUBSCRIBERS']).delete()
        response = db.Table(app.config['SUBSCRIPTIONS']).delete()
        response = db.Table(app.config['LOG']).delete()
        print('Cleaned the db.')
    except Exception as e:
        print(e)
        print('There has been error, probably because no tables currently '
              'exist. Skipping the clean process.')

# Create the db tables required and perform any other db setup.
if args.setup:
    print('Creating dev db')

    # Create the client for the local database
    db = boto3.client(
        'dynamodb',
        endpoint_url='http://dynamodb:8000',
        region_name='eu_west'
    )

    # Create the required tables in the database
    response = db.create_table(
        TableName=app.config['SUBSCRIBERS'],
        AttributeDefinitions=[
            {'AttributeName': 'id', 'AttributeType': 'S'},
            {'AttributeName': 'email', 'AttributeType': 'S'}
        ],
        KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        },
        GlobalSecondaryIndexes=[{
            'IndexName': 'email-index',
            'KeySchema': [{
                'AttributeName': 'email',
                'KeyType': 'HASH'
            }],
            'Projection': {'ProjectionType': 'ALL'},
            'ProvisionedThroughput': {
                'ReadCapacityUnits': 1,
                'WriteCapacityUnits': 1
            }
        }],
    )
    print("Table {} status: {}".format(
        app.config['SUBSCRIBERS'],
        response['TableDescription'].get('TableStatus')
    ))

    response = db.create_table(
        TableName=app.config['SUBSCRIPTIONS'],
        AttributeDefinitions=[
            {'AttributeName': 'subscriptionID', 'AttributeType': 'S'},
            {'AttributeName': 'subscriberID', 'AttributeType': 'S'},
            {'AttributeName': 'topicID', 'AttributeType': 'S'}
        ],
        GlobalSecondaryIndexes=[{
            'IndexName': 'topicID-index',
            'KeySchema': [{
                'AttributeName': 'topicID',
                'KeyType': 'HASH'
            }],
            'Projection': {'ProjectionType': 'ALL'},
            'ProvisionedThroughput': {
                'ReadCapacityUnits': 1,
                'WriteCapacityUnits': 1
            }
        }, {
            'IndexName': 'subscriberID-index',
            'KeySchema': [{
                'AttributeName': 'subscriberID',
                'KeyType': 'HASH'
            }],
            'Projection': {'ProjectionType': 'ALL'},
            'ProvisionedThroughput': {
                'ReadCapacityUnits': 1,
                'WriteCapacityUnits': 1
            }
        }],
        KeySchema=[{'AttributeName': 'subscriptionID', 'KeyType': 'HASH'}],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        }
    )
    print("Table {} status: {}".format(
        app.config['SUBSCRIPTIONS'],
        response['TableDescription'].get('TableStatus')
    ))

    response = db.create_table(
        TableName=app.config['LOG'],
        AttributeDefinitions=[
            {'AttributeName': 'id', 'AttributeType': 'S'},
            {'AttributeName': 'message', 'AttributeType': 'S'}
        ],
        KeySchema=[{'AttributeName': 'id', 'KeyType': 'HASH'}],
        ProvisionedThroughput={
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        },
        GlobalSecondaryIndexes=[{
            'IndexName': 'message-index',
            'KeySchema': [{
                'AttributeName': 'message',
                'KeyType': 'HASH'
            }],
            'Projection': {'ProjectionType': 'ALL'},
            'ProvisionedThroughput': {
                'ReadCapacityUnits': 1,
                'WriteCapacityUnits': 1
            }
        }],
    )
    print("Table {} status: {}".format(
        app.config['LOG'],
        response['TableDescription'].get('TableStatus')
    ))

# Put initial fake data into the database.
if args.populate:

    print('Populating the hermes dev db.')

    # Get developer accounts to be inserted into local database.
    path = (os.path.dirname(os.path.realpath(__file__)) +
            '/../.settings/accounts.cfg')
    users_file = open(path, 'r+').read()
    users = ast.literal_eval(users_file) if users_file else {}

    # Create the subscriptions for the developer's accounts.
    for username, user in users.items():
        util.subscribe(
            user['first_name'],
            user['last_name'],
            user['email'],
            'All',
            ['test-emails', 'error-reporting', 'notify-dev'],
            sms=user.get('sms', ''),
            verified=True,
            slack=user.get('slack', '')
        )
        print('Added subscriber: {} {}'.format(
            user['first_name'], user['last_name']
        ))

    print('Populated dev db.')

# Finally list all items in the database, so we know what it is populated with.
if args.list:
    print('Listing data in the database.')
    db = boto3.resource(
        'dynamodb',
        endpoint_url='http://dynamodb:8000',
        region_name='eu_west'
    )
    try:
        # List subscribers.
        subscribers = db.Table(app.config['SUBSCRIBERS'])
        subscribers = subscribers.scan().get("Items", [])
        if subscribers:
            print("Subscribers created:")
            for subscriber in subscribers:
                print("{} {} - {} {}".format(
                    subscriber['first_name'],
                    subscriber['last_name'],
                    subscriber['email'],
                    subscriber.get('sms', '(no sms)')
                ))
        else:
            print("No subscribers exist.")

        # List subscriptions.
        subscriptions = db.Table(app.config['SUBSCRIPTIONS'])
        subscriptions = subscriptions.scan().get("Items", [])
        if subscriptions:
            print("{} subscriptions created".format(len(subscriptions)))
        else:
            print("No subscriptions exist.")

        # List log.
        log = db.Table(app.config['LOG'])
        log = log.scan().get("Items", [])
        if log:
            print("Log created:")
            print(log)
        else:
            print("No log exist.")

    except Exception as e:
        print("Listing failed. Has database been setup?")

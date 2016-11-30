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
import boto3
from meerkat_hermes import app
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
        print(response)
        response = db.Table(app.config['SUBSCRIPTIONS']).delete()
        print(response)
        response = db.Table(app.config['LOG']).delete()
        print(response)
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
    tables = [
        app.config['SUBSCRIBERS'],
        app.config['SUBSCRIPTIONS'],
        app.config['LOG']
    ]
    for table in tables:
        response = db.create_table(
            TableName=table,
            AttributeDefinitions=[
                {'AttributeName': 'username', 'AttributeType': 'S'}
            ],
            KeySchema=[{'AttributeName': 'username', 'KeyType': 'HASH'}],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )
        print(response)

# Put initial fake data into the database.
if args.populate:
    print('Populated dev db with nothing.')

# Finally list all items in the database, so we know what it is populated with.
if args.list:
    print('Listing data in the database.')
    db = boto3.resource(
            'dynamodb',
            endpoint_url='http://dynamodb:8000', region_name='eu_west'
    )
    try:
        # List subscribers.
        subscribers = db.Table(app.config['SUBSCRIBERS'])
        subscribers = subscribers.scan().get("Items", [])
        if subscribers:
            print("Subscribers created:")
            print(subscribers)
        else:
            print("No subscribers exist.")

        # List subscriptions.
        subscriptions = db.Table(app.config['SUBSCRIPTIONS'])
        subscriptions = subscriptions.scan().get("Items", [])
        if subscribers:
            print("Subscriptions created:")
            print(subscriptions)
        else:
            print("No subscriptions exist.")

        # List log.
        log = db.Table(app.config['LOG'])
        log = log.scan().get("Items", [])
        if subscribers:
            print("Log created:")
            print(log)
        else:
            print("No log exist.")

    except Exception as e:
        print("Listing failed. Has database been setup?")

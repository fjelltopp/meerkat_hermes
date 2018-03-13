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
    app.db.drop()

# Create the db tables required and perform any other db setup.
if args.setup:
    app.db.setup()

# Put initial fake data into the database.
if args.populate:

    print('Populating the hermes dev db.')

    try:
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
    except FileNotFoundError:
        print('No developer account details available.')

    print('Populated dev db.')

# Finally list all items in the database, so we know what it is populated with.
if args.list:
    print('Listing data in the database.')
    try:
        # List subscribers.
        subscribers = app.db.get_all(app.config['SUBSCRIBERS'])
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

        # List log.
        log = app.db.get_all(app.config['LOG'])
        if log:
            print("Log created:")
            print(log)
        else:
            print("No log exist.")

    except Exception as e:
        print("Listing failed. Has database been setup?")

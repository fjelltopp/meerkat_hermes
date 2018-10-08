"""
This class manages a resource that gives access to subscribers in the db".
"""

from flask_restful import Resource, reqparse
from flask import Response, current_app
from meerkat_hermes import authorise
import meerkat_hermes.util as util
import boto3
import json
import logging


class Subscribers(Resource):

    decorators = [authorise]

    def __init__(self):
        # Load the database and tables once upon object creation.
        db = boto3.resource(
            'dynamodb',
            endpoint_url=current_app.config['DB_URL'],
            region_name='eu-west-1'
        )
        self.subscribers = db.Table(current_app.config['SUBSCRIBERS'])

    def get(self, country):
        """
        Get multiple subscribers from the database according the country the
        subscriber is part of.

        Args:
            country (string): the deployment that the subscribers should be
                subscribed toself.
        """
        logging.warning(country)
        # Query DB for all subscribers belonging to a particular country.
        subscribers = self.get_all(country, None)
        # TODO: Format the return data.
        logging.warning(subscribers)
        # TODO: Return the data.
        return subscribers

    def get_all(self, countries, attributes):
        """
        Fetches from the database the requested attributes for all subscribers
        that belong to the specified country. If country or attributes equate
        to false then all possible options for that argument will be used.

        Args:
            country ([str]) A list of countries for which we want user
                accounts. This is an OR list - i.e. any account attached to ANY
                of the countries in the list is retruned.
            attributes ([str]) A list of user account attribute names that we
                want to download.

        Returns:
            A python dictionary storing user accounts by username.
        """

        # Set things up.
        logging.info('Loading subscribers for ' + str(countries) + ' from database.')

        # Allow any value for attributes and countries that equates to false.
        if not attributes:
            attributes = []
        if not countries:
            countries = []

        # If a single value is specified, not a list, turn it into a list.
        if not isinstance(countries, list):
            countries = [countries]
        if not isinstance(attributes, list):
            attributes = [attributes]

        # Include the "All" wildcard [NOTE: Is this really used?]
        countries = countries + ['All']

        # Return dict is indexed by username, so ensure added.
        if attributes and 'id' not in attributes:
            attributes.append('id')

        # Assemble scan arguments programatically, by building a dictionary.
        kwargs = {}

        # Include AttributesToGet if any are specified.
        # By not including them we get them all.
        if attributes:
            kwargs["AttributesToGet"] = attributes

        if not countries:
            # If no country is specified, get all users and return as list.
            return self.subscribers.scan(**kwargs).get("Items", [])

        else:
            subscribers = {}
            # Load data separately for each country
            # ...because Scan can't perform OR on CONTAINS
            for country in countries:

                kwargs["ScanFilter"] = {
                    'country': {
                        'AttributeValueList': [country],
                        'ComparisonOperator': 'CONTAINS'
                    }
                }
                logging.warning(kwargs)
                logging.warning(self.subscribers.scan(**kwargs).get("Items", []))

                # Get and combine the subscribers together in a no-duplications dict.
                for subscriber in self.subscribers.scan(**kwargs).get("Items", []):
                    subscribers[subscriber["id"]] = subscriber

            # Convert the dict to a list by getting values.
            return list(subscribers.values())

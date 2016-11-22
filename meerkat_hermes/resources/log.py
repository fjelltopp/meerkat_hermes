"""
This class enables management of the message log.  It includes methods to get
the entire log or to get a single
"""
import boto3
import json
from flask_restful import Resource
from flask import Response, current_app
from meerkat_hermes.authentication import require_api_key


# The Subscriber resource has two methods - create and delete user.
class Log(Resource):

    # Require authentication
    decorators = [require_api_key]

    def __init__(self):
        # Load the database and tables, upon object creation.
        db = boto3.resource(
            'dynamodb',
            endpoint_url=current_app.config['DB_URL'],
            region_name='eu-west-1'
        )
        self.log = db.Table(current_app.config['LOG'])

    def get(self, log_id):
        """
        Get message log records from the database.

        Args:
             log_id (str): The id of the desired message log.

        Returns:
             The amazon dynamodb response.
        """

        response = self.log.get_item(
            Key={
                'id': log_id
            }
        )
        if 'Item' in response:
            return Response(json.dumps(response),
                            status=200,
                            mimetype="application/json")
        else:
            message = {"message": "400 Bad Request: log_id doesn't exist"}
            return Response(json.dumps(message),
                            status=200,
                            mimetype="application/json")

    def delete(self, log_id):
        """
        Delete a log record from the database.

        Args:
             log_id (str): for the record to be deleted.

        Returns:
             The amazon dynamodb response.
        """

        log_response = self.log.delete_item(
            Key={
                'id': log_id
            }
        )

        return Response(
            json.dumps(log_response),
            status=log_response['ResponseMetadata']['HTTPStatusCode'],
            mimetype='application/json'
        )

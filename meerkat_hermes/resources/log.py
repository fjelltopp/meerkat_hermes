"""
This class enables management of the message log.  It includes methods to get
the entire log or to get a single
"""
import json
from flask_restful import Resource
from flask import Response
from meerkat_hermes import authorise, app


class Log(Resource):

    decorators = [authorise]

    def get(self, log_id):
        """
        Get message log records from the database.

        Args:
             log_id (str): The id of the desired message log.

        Returns:
             The db response if there is one.
        """

        response = app.db.read(
            app.config['LOG'],
            {'id': log_id}
        )
        if response:
            return Response(json.dumps(response), mimetype="application/json")
        else:
            return Response(
                json.dumps({"message": "400 Bad Request: log_id doesn't exist"}),
                status=400,
                mimetype="application/json"
            )

    def delete(self, log_id):
        """
        Delete a log record from the database.

        Args:
             log_id (str): for the record to be deleted.

        Returns:
             The db response if there is one.
        """

        return Response(
            json.dumps(app.db.delete(app.config['LOG'], {'id': log_id})),
            mimetype='application/json'
        )

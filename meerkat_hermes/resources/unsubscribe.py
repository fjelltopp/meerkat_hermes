"""
This class manages provides a public facing gateway to unsubscribe someone from
the system. Specifically it provides a means for folk who know their subscriber
ID, to unsubscribe themselves. A sutbale link can then be included in all
messages that are sent out.
"""
from flask_restful import Resource
from flask import Response
import meerkat_hermes.util as util


# The Unsubscribe resource has two methods:
# One to throw up a confirmation dialouge and one to delete the subscriber.
class Unsubscribe(Resource):

    def get(self, subscriber_id):
        """
        Returns a page that allows the user to confirm they wish to delete
        their subscriptions

        Args:
             subscriber_id (str): The ID for the subscriber to be unsubscribed.
        Returns:
             The amazon dynamodb response.
        """

        html = ("<html><head><title>Unsubscribe Confirmation</title></head>"
                "<body><H2>Unsubscribe Confirmation</H2>"
                "<p>Are you sure you want to unsubscribe?</p>"
                "<form action='/unsubscribe/" + subscriber_id +
                "' method='POST'><input type='submit' value='Confirm'> "
                "</form> </body> </html>")

        return Response(html,
                        status=200,
                        mimetype='text/html')

    def post(self, subscriber_id):
        """
        Actually performs the deletion.

        Args:
             subscriber_id (str): The ID for the subscriber to be unsubscribed.
        Returns:
             The amazon dynamodb response.
        """

        return util.delete_subscriber(subscriber_id)

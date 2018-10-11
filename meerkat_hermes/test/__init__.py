#!/usr/bin/env python3
"""
Meerkat Hermes Tests

Unit tests for Meerkat Hermes util methods and resource classes.
"""
from boto3.dynamodb.conditions import Key
from unittest import mock
from datetime import datetime
import meerkat_hermes.util as util
import meerkat_hermes
from meerkat_hermes import app
import requests
import json
import unittest
import boto3
import logging
import copy
import time


class MeerkatHermesTestCase(unittest.TestCase):

    # Define the test subscriber
    subscriber = dict(
        first_name='Testy',
        last_name='McTestFace',
        email='success@simulator.amazonses.com',
        sms='01234567891',
        topics=['Test1', 'Test2', 'Test3'],
        country="Test"
    )

    # Define the test message
    message = dict(
        subject='Test email',
        message='Nosetest Message',
        html='Test <b>HTML</b> message',
    )

    @classmethod
    def setup_class(self):
        """Setup for testing"""

        app.config.from_object('meerkat_hermes.config.Testing')
        self.app = meerkat_hermes.app.test_client()

        # Load the database
        db = boto3.resource(
            'dynamodb',
            endpoint_url=app.config['DB_URL'],
            region_name='eu-west-1'
        )
        self.subscribers = db.Table(app.config['SUBSCRIBERS'])
        self.subscriptions = db.Table(app.config['SUBSCRIPTIONS'])
        self.log = db.Table(app.config['LOG'])

        # Only show warning level+ logs from boto3, botocore and nose.
        # Too verbose otherwise.
        logging.getLogger('boto3').setLevel(logging.WARNING)
        logging.getLogger('botocore').setLevel(logging.WARNING)
        logging.getLogger('nose').setLevel(logging.WARNING)

    @classmethod
    def teardown_class(self):
        """
        At the end of testing, clean up any database mess created by the
        tests and log any activity.
        """

        # Ideally nothing should be deleted here
        # This teardown checks that the database is clean.
        # Keep track of # of deletions to log as a warning so dev can check.
        deletedObjects = {
            "subscribers": 0,
            "messages": 0
        }

        # Get rid of any undeleted test subscribers.
        query_response = self.subscribers.query(
            IndexName='email-index',
            KeyConditionExpression=Key('email').eq(
                'success@simulator.amazonses.com'
            )
        )
        with self.subscribers.batch_writer() as batch:
            for subscriber in query_response['Items']:
                batch.delete_item(
                    Key={
                        'id': subscriber['id']
                    }
                )
        deletedObjects['subscribers'] = len(query_response['Items'])

        # Get rid of any test messages that have been logged and not deleted.
        query_response = self.log.query(
            IndexName='message-index',
            KeyConditionExpression=Key('message').eq(self.message['message'])
        )
        with self.log.batch_writer() as batch:
            for message in query_response['Items']:
                batch.delete_item(
                    Key={
                        'id': message['id']
                    }
                )
        deletedObjects['messages'] = len(query_response['Items'])

        # Do the logging only if something has been deleted.
        if sum(deletedObjects.values()) != 0:
            logged = ("TEARING DOWN UTIL TEST CLASS "
                      "SHOULD NOT REQUIRE DELETION:\n")
            for obj in deletedObjects:
                if deletedObjects[obj] != 0:
                    logged += "Deleted " + \
                        str(deletedObjects[obj]) + " " + obj + ".\n"
            meerkat_hermes.app.logger.warning(logged)
            assert False

    def test_util_replace_keywords(self):
        """
        Test the replace keywords utility function that enables mail merge in
        our messages.
        """
        for key in self.subscriber:
            message = "<<" + key + ">>"
            value = str(self.subscriber[key])
            if(key == 'topics'):
                value = "Test1, Test2 and Test3"
            self.assertEquals(value, util.replace_keywords(
                message, self.subscriber))

    def test_util_id_valid(self):
        """
        Test the id_valid utility function that checks whether a message ID
        already exists.
        """
        # Create test message log.
        log = {
            'id': 'testID',
            'destination': [self.subscriber['email']],
            'message': self.message['message'],
            'medium': ['email'],
            'time': util.get_date()
        }
        self.log.put_item(Item=log)

        # Test the id_valid utility function.
        existing_id = log['id']
        nonexisting_id = 'FAKETESTID'
        self.assertFalse(util.id_valid(existing_id))
        self.assertTrue(util.id_valid(nonexisting_id))

        # Delete the created log
        delete_response = self.app.delete('/log/' + log['id'])
        delete_response = json.loads(delete_response.data.decode('UTF-8'))
        print(delete_response)
        self.assertEquals(delete_response['ResponseMetadata'][
                          'HTTPStatusCode'], 200)

    def test_util_check_date(self):
        """Test the create subscriptions utility function."""
        self.assertEquals(
            datetime.fromtimestamp(time.time()).strftime('%Y:%m:%dT%H:%M:%S'),
            util.get_date()
        )

    # TODO: Tests for these util functions would be almost doubled later on:
    #  - log_message()
    #  - send_sms()
    #  - send_email()
    #  - delete_subscriber()
    # Util unit tests therefore havn't been considered a priority for
    # including here.  But it would be nice to write proper unit tests for
    # these functions when we have time.

    def test_subscribe_resource(self):
        """
        Test the Subscribe resource, including the PUT, GET and DELETE methods.
        """

        # Create the test subscribers
        put_response = self.app.put('/subscribe', data=self.subscriber)
        self.assertEquals(put_response.status_code, 200)

        # Get the assigned subscriber id.
        data = json.loads(put_response.data.decode('UTF-8'))
        subscriber_id = data['subscriber_id']
        print("Subscriber ID is " + data['subscriber_id'])

        # Check that the subscriber exists in the data base.
        get_response = self.subscribers.get_item(
            Key={
                'id': data['subscriber_id']
            }
        )
        self.assertEquals(
            self.subscriber['email'], get_response['Item']['email']
        )

        # Try to delete the subscriber.
        delete_response = self.app.delete('/subscribe/badID')
        self.assertEquals(delete_response.status_code, 500)
        delete_response = json.loads(delete_response.data.decode('UTF-8'))
        self.assertEquals(delete_response.get('status'), 'unsuccessful')

        delete_response = self.app.delete('/subscribe/' + subscriber_id)
        self.assertEquals(delete_response.status_code, 200)
        delete_response = json.loads(delete_response.data.decode('UTF-8'))
        self.assertEquals(delete_response.get('status'), 'successful')

    def test_subscribers_resource(self):
        """
        Test the Subscribers resource GET method.
        """

        # Create four test subscribers, each with a specified country
        countries = ['Madagascar', 'Madagascar', 'Madagascar', 'Jordan']
        subscriber_ids = []

        for i in range(0, len(countries)):
            # Create a variation on the test subscriber
            subscriber = self.subscriber.copy()
            subscriber['country'] = countries[i]
            subscriber['first_name'] += str(i)
            # Add the subscriber to the database.
            subscribe_response = self.app.put('/subscribe', data=subscriber)
            subscriber_ids.append(json.loads(
                subscribe_response.data.decode('UTF-8')
            )['subscriber_id'])

        # Get all the Madagascar subscribers
        get_response = self.app.get('/subscribers/Madagascar')
        get_response = json.loads(get_response.data.decode('UTF-8'))
        logging.warning(get_response)
        self.assertEqual(len(get_response), 3)

        # Get all the Jordan subscribers
        get_response = self.app.get('/subscribers/Jordan')
        get_response = json.loads(get_response.data.decode('UTF-8'))
        logging.warning(get_response)
        self.assertEqual(len(get_response), 1)

        # Delete the test subscribers.
        for subscriber_id in subscriber_ids:
            self.app.delete('/subscribe/' + subscriber_id)

    def test_verify_resource(self):
        """
        Test the Verify resource, including the GET, POST and PUT methods.
        """

        # Create the unverified test subscriber
        subscribe_response = self.app.put('/subscribe', data=self.subscriber)
        subscriber_id = json.loads(
            subscribe_response.data.decode('UTF-8'))['subscriber_id']

        # Test PUT method.
        put_data = {'subscriber_id': subscriber_id, 'code': '1234'}
        put_response = self.app.put('/verify', data=put_data)
        self.assertEquals(put_response.status_code, 200)

        # Test POST method for wrong and right code.
        post_data = {'subscriber_id': subscriber_id, 'code': '1231'}
        post_response = self.app.post('/verify', data=post_data)
        post_response = json.loads(post_response.data.decode('UTF-8'))
        self.assertEquals(post_response['matched'], False)

        post_data = {'subscriber_id': subscriber_id, 'code': '1234'}
        post_response = self.app.post('/verify', data=put_data)
        post_response = json.loads(post_response.data.decode('UTF-8'))
        self.assertEquals(post_response['matched'], True)

        # Test GET method, for unverified and verified user.
        get_response = self.app.get('/verify/' + subscriber_id)
        self.assertEquals(get_response.status_code, 200)

        get_response = self.app.get('/verify/' + subscriber_id)
        self.assertEquals(get_response.status_code, 400)

        # Delete the user
        self.app.delete('/subscribe/' + subscriber_id)

    def test_unsubscribe_resource(self):
        """
        Test the Unsubscribe resource, including the GET and POST methods.
        """

        # Create the test subscriber
        subscribe_response = self.app.put('/subscribe', data=self.subscriber)
        subscriber_id = json.loads(
            subscribe_response.data.decode('UTF-8')
        )['subscriber_id']

        # Test GET method
        get_response = self.app.get('/unsubscribe/' + subscriber_id)
        self.assertIn("sure you want to unsubscribe",
                      get_response.data.decode('UTF-8'))

        # Test POST method
        post_response = self.app.post('/unsubscribe/' + subscriber_id)
        self.assertIn("successfully unsubscribed",
                      post_response.data.decode('UTF-8'))

        # Delete the user
        self.app.delete('/subscribe/' + subscriber_id)

    def test_email_resource(self):
        """
        Test the Email resource PUT method, using the Amazon SES Mailbox
        Simulators.
        """

        # Create the test subscriber
        subscribe_response = self.app.put('/subscribe', data=self.subscriber)
        subscriber_id = json.loads(
            subscribe_response.data.decode('UTF-8')
        )['subscriber_id']

        # Test the PUT method using an email address.
        email = {**self.message, **{"email": self.subscriber['email']}}
        put_response = self.app.put('/email', data=email)
        put_response = json.loads(put_response.data.decode('UTF-8'))
        self.assertEquals(
            put_response['ResponseMetadata']['HTTPStatusCode'], 200
        )

        # Check that the message has been logged properly.
        log_response = self.log.get_item(
            Key={
                'id': put_response['log_id']
            }
        )
        self.assertEquals(
            log_response['Item']['destination'][0], email['email']
        )

        # Delete the message from the log
        self.app.delete('/log/' + put_response['log_id'])

        # Test the PUT method using a subscriber ID.
        email = {**self.message, **{"subscriber_id": subscriber_id}}
        put_response = self.app.put('/email', data=email)
        put_response = json.loads(put_response.data.decode('UTF-8'))
        self.assertEquals(put_response['ResponseMetadata'][
                          'HTTPStatusCode'], 200)

        # Check that the message has been logged properly.
        log_response = self.log.get_item(
            Key={
                'id': put_response['log_id']
            }
        )
        self.assertEquals(
            log_response['Item']['destination'][0], self.subscriber['email']
        )

        # Delete the user
        self.app.delete('/subscribe/' + subscriber_id)

        # Delete the message from the log
        self.app.delete('/log/' + put_response['log_id'])

    def test_log_resource(self):
        """Test the Log resource GET and Delete methods."""

        # Create test message log.
        log = {
            'id': 'testID',
            'destination': [self.subscriber['email']],
            'message': self.message['message'],
            'medium': ['email'],
            'time': util.get_date()
        }
        self.log.put_item(Item=log)

        # Test the GET Method
        get_response = self.app.get('/log/' + log['id'])
        get_response = json.loads(get_response.data.decode('UTF-8'))
        print(get_response)
        self.assertEquals(get_response['Item']['destination'][
                          0], self.subscriber['email'])
        self.assertEquals(get_response['Item'][
                          'message'], self.message['message'])

        # Test the DELETE Method
        delete_response = self.app.delete('/log/' + log['id'])
        delete_response = json.loads(delete_response.data.decode('UTF-8'))
        print(delete_response)
        self.assertEquals(
            delete_response['ResponseMetadata']['HTTPStatusCode'],
            200
        )

    @mock.patch('meerkat_hermes.util.boto3.client')
    def test_sms_resource(self, sns_mock):
        """
        Test the SMS resource PUT method, using the fake response returned
        by util.send_sms().
        """

        sms = {
            "message": self.message['message'],
            "sms": self.subscriber['sms']
        }

        # Create the mock response.
        sns_mock.return_value.publish.return_value = {
            "ResponseMetadata": {
                "RequestId": "c13d1005-2433-55e0-91bc-4236210aa11c",
                "HTTPStatusCode": 200,
                "HTTPHeaders": {
                    "x-amzn-requestid": "c13d1005-2433-55e0-91bc-4236210aa11c",
                    "content-type": "text/xml",
                    "date": "Wed, 13 Sep 2017 10:05:45 GMT",
                    "content-length": "294"
                },
                "RetryAttempts": 0
            },
            "log_id": "G2c820c31a05b4da593c689bd8c534c82",
            "MessageId": "edd4bd71-9ecf-5ebc-9d5c-ef429bf6da40"
        }

        # Test PUT method.
        put_response = self.app.put('/sms', data=sms)
        put_response = json.loads(put_response.data.decode('UTF-8'))

        self.assertTrue(sns_mock.return_value.publish)
        sns_mock.return_value.publish.assert_called_with(
            Message=sms['message'],
            PhoneNumber=sms['sms'],
            MessageAttributes={
                'AWS.SNS.SMS.SenderID': {
                    'DataType': 'String',
                    'StringValue': app.config['FROM']
                }
            }
        )

        self.assertEquals(
            put_response['ResponseMetadata']['RetryAttempts'],
            0
        )
        self.assertEquals(
            put_response['ResponseMetadata']['HTTPStatusCode'],
            200
        )

        # Check that the message has been logged properly.
        log_response = self.log.get_item(
            Key={
                'id': put_response['log_id']
            }
        )
        self.assertEquals(log_response['Item']['destination'][0], sms['sms'])

        # Delete the message from the log
        self.app.delete('/log/' + put_response['log_id'])

    @mock.patch('meerkat_hermes.util.requests.post')
    def test_gcm_resource(self, request_mock):
        """
        Test the GCM resource PUT method, using the fake response returned
        by util.send_gcm().
        """

        gcm = {
            "message": self.message['message'],
            "destination": '/topics/demo'
        }

        # Create the mock response.
        dummyResponseDict = {
            "multicast_id":123456,
            "success":1,
            "failure":0,
            "canonical_ids":0,
            "results":[{"message_id":"0:abc123"}]
        }

        dummyResponse = requests.Response()
        dummyResponse.status_code = 200
        dummyResponse._content = json.dumps(dummyResponseDict).encode()
        request_mock.return_value = dummyResponse

        # Test PUT method.
        put_response = self.app.put('/gcm', data=gcm)
        put_response = json.loads(put_response.data.decode('UTF-8'))

        call_data = {
            "data":
            {"message": self.message['message']},
            "to": "/topics/demo"}

        call_headers={
            'Content-Type': 'application/json',
            'Authorization': 'key='+app.config['GCM_AUTHENTICATION_KEY']}

        self.assertTrue(request_mock.called)
        request_mock.assert_called_with('https://gcm-http.googleapis.com/gcm/send',
            data=json.dumps(call_data),
            headers=call_headers)

        self.assertEquals(put_response['success'], 1)

        # Check that the message has been logged properly.
        log_response = self.log.get_item(
            Key={
                'id': put_response['log_id']
            }
        )
        print(str(log_response))
        self.assertEquals(log_response['Item']['destination'], gcm['destination'])

        # Delete the message from the log
        self.app.delete('/log/' + put_response['log_id'])

    @mock.patch('meerkat_hermes.util.boto3.client')
    def test_publish_resource(self, boto_mock):
        """Test the Publish resource PUT method."""

        def clones(object, times=None):
            # Generator to yield clones of an object, infitnely or <n times.
            # Used to generate nexmo response for the mock_sms_response
            if times is None:
                while True:
                    yield copy.copy(object)
            else:
                for i in range(times):
                    yield copy.copy(object)

        # Createfour test subscribers, each with subscriptions to a different
        # list of topics.
        topic_lists = [
            ['Test1', 'Test2'],
            ['Test1'],
            ['Test2'],
            ['Test3'],
            ['Test1']
        ]
        subscriber_ids = []

        for i in range(0, len(topic_lists)):
            # Create a variation on the test subscriber
            subscriber = self.subscriber.copy()
            subscriber['topics'] = topic_lists[i]
            subscriber['first_name'] += str(i)
            # Remove the SMS field from three of the subscribers
            if(i % 2 != 0):
                del subscriber['sms']
            # Create an unverified subscriber
            if i is not 4:
                subscriber['verified'] = True
            # Add the subscriber to the database.
            subscribe_response = self.app.put('/subscribe', data=subscriber)
            subscriber_ids.append(json.loads(
                subscribe_response.data.decode('UTF-8')
            )['subscriber_id'])

        # Create the mock response.
        boto_mock.return_value.publish.side_effect = clones({
            "ResponseMetadata": {
                "RequestId": "c13d1005-2433-55e0-91bc-4236210aa11c",
                "HTTPStatusCode": 200,
                "HTTPHeaders": {
                    "x-amzn-requestid": "c13d1005-2433-55e0-91bc-4236210aa11c",
                    "content-type": "text/xml",
                    "date": "Wed, 13 Sep 2017 10:05:45 GMT",
                    "content-length": "294"
                },
                "RetryAttempts": 0
            },
            "log_id": "G2c820c31a05b4da593c689bd8c534c82",
            "MessageId": "edd4bd71-9ecf-5ebc-9d5c-ef429bf6da40"
        })

        boto_mock.return_value.send_email.side_effect = clones({
            "MessageId": "0102015e7afbfec3-cf8df94b-81bc-4c9b5966a4-000000",
            "ResponseMetadata": {
                "RequestId": "270fa909-9876-11e7-a0db-e3a14f067914",
                "HTTPStatusCode": 200,
                "HTTPHeaders": {
                    "x-amzn-requestid": "270fa909-9876-11e7-a0db-e3a14f067914",
                    "content-type": "text/xml",
                    "date": "Wed, 13 Sep 2017 11:24:48 GMT",
                    "content-length": "326"
                },
                "RetryAttempts": 0
            },
            "log_id": "G891694c3d4364f89bb124e31bfb15b58",
        })

        # Create the message.
        message = self.message.copy()
        message['html-message'] = message.pop('html')
        message['medium'] = ['email', 'sms']

        # Keep track of the message IDs so we can delete the logs afterwards.
        message_ids = []

        # Test the PUT Method with different calls.
        # -----------------------------------------

        # Publish the test message to topic Test4.
        message['topics'] = ['Test4']
        message['id'] = "testID1"
        message_ids.append(message['id'])
        put_response = self.app.put('/publish', data=message)
        put_response = json.loads(put_response.data.decode('UTF-8'))
        print(put_response)

        # No subscribers have subscribed to 'Test4'.
        # No messages should be sent
        # Check that no messages have been sent and that the sms response has
        # not been called.
        self.assertEquals(len(put_response), 0)
        self.assertFalse(boto_mock.return_value.publish.called)

        # Publish the test message to topic Test3.
        message['topics'] = ['Test3']
        message['id'] = "testID2"
        message_ids.append(message['id'])
        put_response = self.app.put('/publish', data=message)
        put_response = json.loads(put_response.data.decode('UTF-8'))
        print("Response to publishing message to topic: " +
              str(message['topics']) + "\n" + str(put_response))

        # Only subscriber 4 has subscription to 'Test3'.
        # Subscriber 4 hasn't given an SMS number, so only one email is sent.
        # Check only one email is sent and no sms calls are made.
        print(put_response)
        self.assertEquals(len(put_response), 1)
        self.assertFalse(boto_mock.return_value.publish.called)
        self.assertEquals(put_response[0]['Destination'][
                          0], self.subscriber['email'])

        # Publish the test message to topic Test1.
        message['topics'] = ['Test1']
        message['id'] = "testID3"
        message_ids.append(message['id'])
        put_response = self.app.put('/publish', data=message)
        put_response = json.loads(put_response.data.decode('UTF-8'))
        print("Response to publishing message to topic: " +
              str(message['topics']) + "\n" + str(put_response))

        # Subscriber 1 and 2 have subscriptions to 'Test1'.
        # Subscriber 5 is unverified so gets no messages.
        # Subscriber 2 hasn't given an SMS number, so 2 emails and 1 sms sent.
        # Check three messages sent in total and sms mock called once.
        self.assertEquals(len(put_response), 3)
        self.assertTrue(boto_mock.return_value.publish.call_count == 1)

        # Publish the test message to both topics Test1 and Test2.
        message['topics'] = ['Test1', 'Test2']
        message['id'] = "testID4"
        message_ids.append(message['id'])
        put_response = self.app.put('/publish', data=message)
        put_response = json.loads(put_response.data.decode('UTF-8'))
        print("Response to publishing message to topic: " +
              str(message['topics']) + "\n" + str(put_response))

        # Sub 1 subscribed to 'Test1' and 'Test2' but only gets 1 sms & email.
        # Sub 2 subscribed to 'Test1' but no sms, so gets just one email.
        # Sub 3 subscribed to 'Test2' gets 1 email and sms.
        # Sub 5 subscriber to 'Test1' but unverified so gets no messages.
        # Note that the publish resource removes duplications for subscriber 1.
        # This results in 4 messages to sub 1, 1 to sub 2, and 2 to sub 3.
        # Check number of messages sent is 7 and that sms mock has been called
        # ANOTHER 2 times (i.e. called 1+2=3 times in total)
        self.assertEquals(len(put_response), 5)
        self.assertTrue(boto_mock.return_value.publish.call_count == 3)

        # Delete the logs.
        for message_id in message_ids:
            self.app.delete('/log/' + message_id)

        # Delete the test subscribers.
        for subscriber_id in subscriber_ids:
            self.app.delete('/subscribe/' + subscriber_id)

        # Test whether the publish resources squashes requests when they exceed
        # the rate limit.  Already called 4 times so set the limit to 4 and
        # check that a 5th attempt to publish fails....
        app.config['PUBLISH_RATE_LIMIT'] = 4
        message['topics'] = ['Test4']
        message['id'] = "testID1"
        message_ids.append(message['id'])
        put_response = self.app.put('/publish', data=message)
        put_response_json = json.loads(put_response.data.decode('UTF-8'))
        print(put_response_json)
        print(put_response)
        self.assertEquals(put_response.status_code, 503)
        self.assertTrue(put_response_json.get('message', False))
        app.config['PUBLISH_RATE_LIMIT'] = 20

# TODO Test Error and Notify Resources

if __name__ == '__main__':
    unittest.main()

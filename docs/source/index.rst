==============
Meerkat Hermes
==============

**Meerkat Hermes** is our purpose-built messaging module, that sends emails and SMS messages to those who have "subscribed" to receive them. Users subscribe to "topics", which the software then "publishes" messages to. The module is designed as a REST API using Python Flask.

---------
Structure
---------

Meerkat Hermes is built using **Flask RESTful** - an extension for Flask that adds support for quickly building REST APIs.  The Python package is split into "resources" and "utilities".  The *resources* define the response to each URL endpoint, whilst the *utilities* provide functionaility to support the *resources*. Each resource is a Python class stored in a seperate Python file under *meerkat_hermes/resources*.  Each *resource* is built  on top of **Flask pluggable-views**, providing easy access to HTTP methods such as *GET, PUT, POST* and *DELETE*.  Each resource class therefore defines functions that respond to each HTTP method made available by the resource. The resource class is then added to the Flask app at the desired URL endpoint in the *__init__.py* file.

**Flask RESTful** handles argument parsing of data provided by the HTTP request. The data should be provided in JSON format and include the Meerkat Hermes API key under the field "api_key". The arguments required in this data are specified in the Python docs. An error is thrown if the data does not confirm to the parser's requirements.

The folder structure is simple and looks like this:

**meerkat_hermes/**

   **authentication.py** Defines a decorator that requires API key authentication before proceeding with the desired function.

   **__init__.py** Initialises the Flask app and adds the resources to the desired URL end points.

   **resources/**  A folder containing the resources for the REST API, as required by **Flask RESTful**.

   **test/** A folder containing our testing harness for meerkat_hermes.

   **util/** A folder containing utility functionality to support the resources.

-----------------------------
Third Party Software Services
-----------------------------

Meerkat Hermes depends on some major external software services to send SMS messages, emails and store data. It would have been nice to keep all required software services within Amazon Web Services (AWS), however at the time of writting AWS does not provide a means of sending SMS messages to numbers outside the states. Should this change in the future, it may be desirable to consolidate our third party services in one place.  At the moment Meerkat Hermes uses Nexmo to send SMS messages, and Amazon SES to send email messages. The Python package Boto3 is used to connect with AWS, whilst Nexmo provides a REST API to which standard HTTP requests can be made.

Meerkat Hermes stores data in Amazon's DynamoDB service.  DynamoDB is a non-relational database service that forms part of Amazon Web Services.  Meerkat Hermes uses three tables in DynamoDB:

  * **hermes_subscribers** stores details about each subscriber in the system. This includes their first and last name, their email address, optionally their sms number, their unique subscriber UUID, whether or not their contact details have been verified, and finally the topics they wish to subscribe to.

  * **hermes_subscriptions** maps topics to subscribers.  Each row, or subscription, maps a single topic ID to a single subscriber ID.  It is used to optimise searches over topic IDs when determining who should receive a given message.

  * **hermes_log** logs details all the messages sent by hermes, and helps to ensure duplicate messages arn't sent.

--------
Features
--------

When the **Subscribe resource** `PUT` method is called, a new subscriber is created and assigned a UUID, reffered to as the subscriber ID, which is returned to the caller. A new subscriber typically has "unverified" contact details at this point. Subscriptions are only created upon a subscriber's contact details being verified.  The means their details are in the database, and can be directly messaged using the *Email* or *SMS* resource, but they will not receive any messages sent using the *Publish* resource (read on for more details).

The **Verify resource** implements three HTTP methods: `PUT`, `POST` and `GET`.  The `PUT` method allows the caller to assign a "verification code" to the given subscriber in the database. The `POST` method allows a user to compare a given code against the code stored in the database. The `GET` method sets the Subscriber's record as "verified" and creates the necessary subscriptions in the subscription table.  This resource can therefore be securely used verify any communication medium.

There are three resources that can be used to send a message out: the **Email**, **SMS** and **Publish resources**. All three resources log details of the sent message in the hermes_log table.  The **Log resource** provides a means of viewing (the `GET'` method) and deleting (the `DELETE` method) message logs.  The Email and SMS resoucres just send a given email or sms message to a given list of destinations. The destinations can either be directly specified as an email addresses or sms numbers respectively, or alternatively as subscriber IDs. These resources are used for sending out verification messages and other one-off messages that may be required by the Meerkat project.

The **Publish resource** is the workhorse of Meerkat Hermes.  It takes a given message and "publishes" it to a given topic, by sending the message to all subscribers with a subscription matching the given topic ID. **NOTE: Meerkat Hermes does not "understand" the topic IDs in any way - they are just strings.  It is up to the subscribers and publishers to agree on a format for building topic ID strings.**  It is perfectly possible to subscribe to a topic no-one is publishing to, and to publish to a topic no-one is subscribing to.

It is worth noting that there is **mail-merge functionality** built into the Publish resource. Any subscriber field, such as first name or last name, can be referenced in the message by wrapping the field title in double angle brackets e.g. <<first_name>> and <<last_name>>.  This means you can personalise messages and build url endpoints in messages based upon the individual subscriber ID.

This is a key principle behind the **Unsubscribe resource**. In each message sent out to a verified subscriber, we link to a URL endpoint that includes the subscriber ID: `/unsubscribe/<subscriber_id>`. This calls the `GET` method of the *Unsubscribe* resource, which presents a simple HTML confirmation form.  Upon submission, this form makes a `POST` request to the same resource which actually deletes the subscriber and their subscriptions.

----------
Deployment
----------

Unlike the other components of the Meerkat Project, Meerkat Hermes is currently only deployed once for all countries.  The single deployment on a seperate Amazon EC2 Server handles all the Meerkat Messaging needs.  No web server is installed on the Hermes server, but uWSGI is required to interface with the Master NGINX EC2 server.  To redeploy Meerkat Hermes on our hermes EC2 server, one simply has to ssh into the server, change directory `/var/www/meerkat_hermes`, pull the master branch of the repository, and finally stop and start uwsgi:
```sudo stop uwsgi-hermes
sudo start uwsgi-hermes ```

------------------
Code Documentation
------------------

The code documentation is available here:

.. toctree::
   :maxdepth: 4

   hermes/util
   hermes/resources
   hermes/flask

------------------
Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

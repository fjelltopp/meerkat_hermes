from meerkat_libs.auth_client import auth
from meerkat_hermes import app
from flask import abort, request
from functools import wraps
import json
import logging


def require_api_key(f):
    """
    @param f: flask function
    @return: decorator, return the wrapped function or abort json object.
    """
    @wraps(f)
    def decorated(*args, **kwargs):

        if request.data:
            app.logger.warning(request.data)
            app.logger.warning(request.data.decode("UTF-8"))
            app.logger.warning(json.loads(request.data.decode("UTF-8")))
            key = json.loads(request.data.decode("UTF-8")).get("api_key", "")
        else:
            app.logger.warning(request.args)
            key = request.args.get("api_key", "")

        app.logger.warning(app.config["API_KEY"])
        app.logger.warning(key)
        app.logger.warning(key == app.config["API_KEY"])

        if not key and app.config["API_KEY"]:
            app.logger.debug('No api_key specified, checking auth instead.')
            auth.check_auth(['hermes'], ['meerkat'])
            return f(*args, **kwargs)

        elif key == app.config["API_KEY"] or not app.config["API_KEY"]:
            app.logger.debug('Using specified API Key to authenticate.')
            return f(*args, **kwargs)

        else:
            logging.debug('Incorrect API Key provided.')
            app.logger.warning(
                "Unauthorized address trying to use API: {}".format(
                    request.remote_addr
                ) + "\nwith api key: " + key
            )
            abort(401)

    return decorated

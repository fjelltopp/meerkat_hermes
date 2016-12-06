from meerkat_hermes import app
from flask import abort, request
from functools import wraps
import json


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
            key = request.args.get("api_key", "")

        if(key == app.config["API_KEY"] or app.config["API_KEY"] == ""):
            return f(*args, **kwargs)
        else:
            app.logger.warning(
                "Unauthorized address trying to use API: {}".format(
                    request.remote_addr
                ) + "\nwith api key: " + key
            )
            abort(401)

    return decorated

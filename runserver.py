#!/usr/bin/env python3
from meerkat_hermes import app
app.run(debug=app.config['DEBUG'], host="0.0.0.0")

# Replace above with following line for production
# app.run(host='0.0.0.0')

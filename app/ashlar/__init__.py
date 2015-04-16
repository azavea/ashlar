#!/usr/bin/env python

# Import flask and template operators
from flask import Flask, render_template

# Import SQLAlchemy
from flask.ext.sqlalchemy import SQLAlchemy

# Define the WSGI application object
app = Flask(__name__)

# Configurations
app.config.from_object('config')

# Define the database object which is imported
# by modules and controllers
# TODO: set up database
db = SQLAlchemy(app)

# Sample HTTP error handling
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

from ashlar import urls

from ashlar.views import hello as hello_module
app.register_blueprint(hello_module)

# Build the database:
# This will create the database file using SQLAlchemy
# db.create_all()
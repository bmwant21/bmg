# -*- coding: utf-8 -*-
class Config(object):
    SECRET_KEY = '{{ secret_key }}'
    STATIC_FOLDER = 'static/'
    DEBUG = True
    RELOADER = True
    RUN_HOST = '127.0.0.1'
    RUN_PORT = {{ run_port }}
    {% if with_db %}
    DB_NAME = '{{ db_name }}'
    {% if db_backend != 'sqlite' %}
    DB_USER = '{{ db_user }}'
    DB_PASS = '{{ db_password }}'
    DB_HOST = '{{ db_host }}'
    DB_PORT = {{ db_port }}
    {% endif %}
    {% endif %}

class DevelopmentConfig(Config):
    """
    Specify all additional configuration variables here.
    Also you can create as many configurations a s you want with their own
    unique parameters.
    """
    pass
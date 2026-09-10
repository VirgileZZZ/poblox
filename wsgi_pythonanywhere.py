# -*- coding: utf-8 -*-
"""
Fichier WSGI pour PythonAnywhere.
À coller dans le "WSGI configuration file" de l'onglet Web,
en remplaçant TON_USER par ton nom d'utilisateur PythonAnywhere.
"""
import sys

path = "/home/TON_USER/recre"
if path not in sys.path:
    sys.path.insert(0, path)

from flask_app import app as application  # noqa

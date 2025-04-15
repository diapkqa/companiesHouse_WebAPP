import os
import string
import hashlib
import json
import requests
import mysql.connector
import pandas as pd
from flask import Flask, request, jsonify, send_file,render_template,redirect
from flask_cors import CORS


API_KEY = "03ed5851-da50-4a59-9c87-d903055fd3e6"
BASE_URL = "https://api.company-information.service.gov.uk"
CACHE_DIR = './cache'
LIMIT = 10
"""Получает данные из внешнего API и извлекает полезные поля."""

import json
import os
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from config import tags_work
from data_work import storage
import requests



API_URL = "https://api.poiskkino.dev"
TOKEN = os.getenv("POISKKINO_API_KEY")

if TOKEN is None:
    try:
        from api_token import TOKEN
    except ImportError:
        TOKEN = None

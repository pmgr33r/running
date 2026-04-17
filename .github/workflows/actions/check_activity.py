#!/usr/bin/env python3

import json
import os
import sys
from datetime import datetime, timezone

import requests

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
OUTPUT_FILE = "data/status.json"

def refresh_access_token(client_id, client_secret, refresh_token):
  resp = requests.post(STRAVA_TOKEN_URL, data={
    "client_id": client_id,
    "client_secret": client_secret,
    "refresh_token": refresh_token,
    "grant_type": "refresh_token",
  }, timeout=30)
  if resp.status_code != 200:
    print(f"Token refresh failed: {resp.status_code} {resp.text}", file=sys.stderr)
    sys.exit(1)
  data = resp.json()
  return data["access_token"], data.get("refresh_token", refresh_token)

def get_todays_activities(access_token):
  now = datetime.now(timezone.utc)
  start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
  after_epoch = init(start_of_day.timestamp())
  

#!/usr/bin/env python3
"""
check_activity.py - Check Strava for today's activity and write status JSON.

Reads Strava credentials from environment.ini in the same directory.

Usage:
    python check_activity.py
    python check_activity.py --output /path/to/status.json
"""

import argparse
import configparser
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "environment.ini")
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, "..", "output", "strava_status.json")

STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"
STRAVA_ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"


def load_config():
    # Prefer environment variables (for GitHub Actions), fall back to environment.ini (local)
    client_id = os.environ.get("STRAVA_CLIENT_ID", "").strip()
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET", "").strip()
    refresh_token = os.environ.get("STRAVA_REFRESH_TOKEN", "").strip()

    if all([client_id, client_secret, refresh_token]):
        return client_id, client_secret, refresh_token

    if not os.path.exists(CONFIG_FILE):
        print(f"Set STRAVA_CLIENT_ID/STRAVA_CLIENT_SECRET/STRAVA_REFRESH_TOKEN env vars,", file=sys.stderr)
        print(f"or create config file: {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)

    if "STRAVA" not in config:
        print("Missing [STRAVA] section in environment.ini", file=sys.stderr)
        sys.exit(1)

    section = config["STRAVA"]
    client_id = section.get("CLIENT_ID", "").strip()
    client_secret = section.get("CLIENT_SECRET", "").strip()
    refresh_token = section.get("REFRESH_TOKEN", "").strip()

    if not all([client_id, client_secret, refresh_token]):
        print("Missing CLIENT_ID, CLIENT_SECRET, or REFRESH_TOKEN", file=sys.stderr)
        sys.exit(1)

    return client_id, client_secret, refresh_token


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
    after_epoch = int(start_of_day.timestamp())

    resp = requests.get(STRAVA_ACTIVITIES_URL, headers={
        "Authorization": f"Bearer {access_token}",
    }, params={
        "after": after_epoch,
        "per_page": 10,
    }, timeout=30)

    if resp.status_code != 200:
        print(f"Activities fetch failed: {resp.status_code} {resp.text}", file=sys.stderr)
        sys.exit(1)

    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="Check Strava for today's activity")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Path to write status JSON")
    args = parser.parse_args()

    client_id, client_secret, refresh_token = load_config()

    access_token, new_refresh_token = refresh_access_token(client_id, client_secret, refresh_token)

    if new_refresh_token != refresh_token:
        print("Refresh token rotated. Updating secret via gh CLI.")
        result = subprocess.run(
            ["gh", "secret", "set", "STRAVA_REFRESH_TOKEN", "--body", new_refresh_token],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"Failed to update secret: {result.stderr}", file=sys.stderr)
        else:
            print("STRAVA_REFRESH_TOKEN secret updated.")

    activities = get_todays_activities(access_token)

    now_utc = datetime.now(timezone.utc).isoformat()
    status = {
        "checked_at": now_utc,
        "activity_logged": len(activities) > 0,
        "activity_count": len(activities),
        "activities": [
            {
                "name": a.get("name", ""),
                "type": a.get("type", ""),
                "distance_miles": round(a.get("distance", 0) / 1609.34, 2),
                "moving_time_minutes": round(a.get("moving_time", 0) / 60, 1),
                "start_time": a.get("start_date_local", ""),
            }
            for a in activities
        ],
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(status, f, indent=2)

    label = "YES" if status["activity_logged"] else "NO"
    print(f"Activity today: {label} ({status['activity_count']} activities)")
    print(f"Status written to: {args.output}")


if __name__ == "__main__":
    main()

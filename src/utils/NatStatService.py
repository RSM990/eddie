from dotenv import load_dotenv
import os
import requests
import json
from datetime import datetime
import time


class NatStatService:
    load_dotenv()

    def __init__(self):
        self.nat_stat_url = os.getenv('NAT_STAT_URL')
        self.nat_stat_key = os.getenv('NAT_STAT_KEY')

    def get_url(self, league_name, resource):
        url = f"{self.nat_stat_url}/{self.nat_stat_key}/{resource}/{league_name}"
        return url

    def get_full_response_by_url(self, url):
        # print(url)
        get_request = requests.get(url)
        if get_request.ok:
            response = json.loads(get_request.content)
            user_data = response.get("user")
            rate_limit_remaining = int(user_data.get("ratelimit-remaining"))
            if rate_limit_remaining < 10:
                rate_limit_reset = user_data.get("ratelimit-reset")
                self.wait_for_rate_limit(rate_limit_reset)
            return response

    def get_full_response(self, league, resource, search_param):
        league_name = self.translate_league_name(league["name"])
        url = f"{self.nat_stat_url}/{self.nat_stat_key}/{resource}/{league_name}/{search_param}"
        return self.get_full_response_by_url(url)

    def get_data(self, league, resource, search_param):
        response = self.get_full_response(league, resource, search_param)
        if response["success"] == "1":
            data = response[resource]
            for key, value in data.items():
                if value is None:
                    continue
                return value
        else:
            return None

    @staticmethod
    def is_successful_response(response):
        return response["success"] == "1"

    @staticmethod
    def get_next_url(response):
        meta = response['meta']
        url = meta.get('page-next')
        return url

    @staticmethod
    def wait_for_rate_limit(rate_limit_reset):
        datetime_format = "%Y-%m-%d %H:%M:%S"

        reset_date = datetime.strptime(rate_limit_reset, datetime_format)

        time_difference = reset_date - datetime.now()
        seconds_until_reset = time_difference.total_seconds() + 45
        print(f"RATE LIMIT -- Waiting ${seconds_until_reset} seconds for Nat Stat rate limit reset")
        time.sleep(seconds_until_reset)

    @staticmethod
    def translate_league_name(league_name):
        if league_name == "NFL":
            return "PFB"

        return league_name

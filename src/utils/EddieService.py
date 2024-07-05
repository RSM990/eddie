import requests
import json
from dotenv import load_dotenv
import os
from typing import Optional


class EddieService:
    load_dotenv()

    def __init__(self):
        self.eddie_url = os.getenv('EDDIE_URL')
        self.settings_id = os.getenv('SETTINGS_ID')

    def get_data(self, path, data_key: Optional[str] = None):
        request = requests.get(f"{self.eddie_url}/{path}")
        if request.ok:
            response = json.loads(request.content)
            if response.get('status') == "success":
                data = response.get('data')
                if data_key is None:
                    data_key = path
                return data.get(data_key)
            else:
                return None

    def post_data(self, path, body):
        url = f"{self.eddie_url}/{path}"
        requests.post(url, json=body)

    def patch_data(self, resource, resource_id, update_body):
        update_url = f"{self.eddie_url}/{resource}/{resource_id}"
        requests.patch(update_url, json=update_body)

    def get_settings_value(self, key):
        eddie_settings = self.get_data('settings')
        if eddie_settings is not None:
            value = eddie_settings[0].get(key)
            if value is None:
                print(f"No settings found for key: {key}")
            return value
        else:
            print("No Settings document found - something has gone wrong")
            return None

    def update_settings_value(self, key, value):
        update_request = {
            key: value
        }
        self.patch_data('settings', self.settings_id, update_request)

    @staticmethod
    def get_full_response(url):
        request = requests.get(url)
        if request.ok:
            response = json.loads(request.content)
            if response.get('status') == "success":
                return response
            else:
                return None


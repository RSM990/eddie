from urllib.parse import urlparse, parse_qs


class Helpers:

    @staticmethod
    def parse_empty_dict_to_none(data):
        if isinstance(data, dict) and not data:
            return None
        return data

    @staticmethod
    def get_query_string_value(url, key):
        # Parse the URL
        parsed_url = urlparse(url)

        # Parse the query string
        query_params = parse_qs(parsed_url.query)

        # Get the value of the 'page' parameter
        return query_params.get(key, [None])[0]

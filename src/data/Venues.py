from src.data.Leagues import Leagues
from src.utils.EddieService import EddieService
from src.utils.NatStatService import NatStatService


class Venues:
    def __init__(self):
        self.resource = "venues"
        self.eddie_service = EddieService()
        self.nat_stat_service = NatStatService()
        self.venue_codes = self.load_venue_code_lookup()
        self.league_service = Leagues()

    def load_venue_code_lookup(self):
        url = "venues?limit=1000"
        venues = self.eddie_service.get_data(url, 'venues')

        return dict((x.get("natStatCode"), x.get("_id")) for x in venues)

    def get_venue_id_from_code(self, venue_code):
        venue = self.venue_codes.get(venue_code)
        if venue is None:
            print(f"could not find venue for code: {venue_code}")
        return venue

    @staticmethod
    def parse_venue(response_data):
        return {
            "natStatCode": response_data.get('code'),
            "name": response_data.get('name'),
            "location": response_data.get('location'),
            "country": response_data.get('country'),
            "latitude": response_data.get('latitude'),
            "longitude": response_data.get('longitude'),
            "description": response_data.get('description'),
            "homeOfThe": response_data.get('homeofthe'),
            "capacity": response_data.get('capacity'),
            "yearOpened": response_data.get('yearopened'),
            "yearClosed": response_data.get('yearclosed')
        }

    def load_venues(self):
        for league in self.league_service.get_leagues():
            league_name = self.nat_stat_service.translate_league_name(league["name"])
            print(f'Getting {self.resource} for {league_name}')

            url = self.nat_stat_service.get_url(league_name, self.resource)
            while url is not None:
                response = self.nat_stat_service.get_full_response_by_url(url)
                if response["success"] == "1":
                    venues = response[self.resource]
                    for key, value in venues.items():
                        if value:
                            nat_code = value['code']
                            if nat_code not in self.venue_codes:
                                post_request = self.parse_venue(value)
                                self.eddie_service.post_data(self.resource, post_request)
                                self.venue_codes[nat_code] = post_request.get('name')

                    url = self.nat_stat_service.get_next_url(response)
                else:
                    break

    def get_venue(self, nat_stat_venue_code):
        if nat_stat_venue_code is None:
            return None

        path = f"venues?natStatCode={nat_stat_venue_code}"
        venues = self.eddie_service.get_data(path, self.resource)
        if len(venues) > 0:
            return venues[0].get("_id")


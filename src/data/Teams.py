from src.data.Leagues import Leagues
from src.data.Venues import Venues
from src.utils.EddieService import EddieService
from src.utils.NatStatService import NatStatService


class Teams:
    def __init__(self):
        self.resource = "teams"
        self.league_service = Leagues()
        self.venue_service = Venues()
        self.nat_stat_service = NatStatService()
        self.eddie_service = EddieService()
        self.team_code_lookup = self.load_team_code_dictionary()

    def load_team_code_dictionary(self):
        path = f"{self.resource}?limit=1000&fields=code,_id"
        teams = self.eddie_service.get_data(path, self.resource)
        return dict((f"{x.get('league').get('_id')}_{x.get('code')}", x.get("_id")) for x in teams)

    def get_team_from_code(self, league_id, team_code):
        team_lookup_code = f"{league_id}_{team_code}"
        team = self.team_code_lookup .get(team_lookup_code)
        if team is None:
            print(f"Could not find team for {team_code} in league {league_id}")
        return team

    def load_teams(self):
        for league in self.league_service.get_leagues():
            league_name = self.nat_stat_service.translate_league_name(league["name"])
            league_id = league["_id"]

            print(f'Getting {self.resource} for {league_name}')

            url = self.nat_stat_service.get_url(league_name, self.resource)
            while url is not None:
                response = self.nat_stat_service.get_full_response_by_url(url)
                if self.nat_stat_service.is_successful_response(response):
                    teams = response[self.resource]
                    for key, team in teams.items():
                        if team:
                            team_code = team['code']
                            if team_code is not None:
                                team_info = self.nat_stat_service.get_data(league_name, self.resource, team_code)
                                for team_key, team_value in team_info.items():
                                    venue = team_value.get('venue')
                                    if venue is not None:
                                        venue_id = self.venue_service.get_venue(venue.get("code"))

                                    post_request = {
                                        "league": league_id,
                                        "name": team.get('name'),
                                        "code": team_code,
                                        "nickname": team_value.get('nickname'),
                                        "city": team_value.get('city'),
                                        "venue": venue_id
                                    }

                                    self.eddie_service.post_data(self.resource, post_request)

                    meta = response['meta']
                    url = meta.get('page-next')
                else:
                    break


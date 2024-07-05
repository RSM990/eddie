from src.utils.EddieService import EddieService


class Leagues:
    def __init__(self):
        self.resource = "leagues"
        self.eddie_service = EddieService()

    def get_leagues(self):
        return self.eddie_service.get_data(self.resource)

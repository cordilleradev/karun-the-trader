from models.opportunity import Opportunity, StellarAsset
from stellar_sdk import Server
import pandas as pd

PATH_TO_BLACKLIST_DATA = "blacklist.csv"
class DataFeed:
    horizon = Server('https://horizon.stellar.org')
    blacklist_data = pd.read_csv(PATH_TO_BLACKLIST_DATA)
    
    def pull_opportunities() -> list[Opportunity]:
        raise NotImplementedError
        
    def is_on_blacklist(self, pool_id : str) -> bool:
        return pool_id in list(self.blacklist_data["pool_id"])



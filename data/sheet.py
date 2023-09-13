from data.client import DataFeed
from models.opportunity import Opportunity, StellarAsset
from stellar_sdk import LiquidityPoolAsset, Asset
import gspread

class SheetFeed(DataFeed):
    def __init__(self, sheet_id : str) -> None:
        super().__init__()
        self.sheet_id = sheet_id
        self.service_account = gspread.service_account("token.json")

    def pull_opportunities(self) -> list[Opportunity]:
        opportunities = []
        for pool in self.get_spreadsheet():
            if (
                len(pool['pool_name']) > 0
                and len(pool['memo']) > 0
                and len(pool['pool_id']) > 0
                and len(pool['reward_asset_type']) > 0
                and pool['daily_reward_amount'] != '' and pool['daily_reward_amount'] > 0
            ):
                reward_asset = StellarAsset(
                    type = "native" if pool['reward_asset_type'] == "native" else "token",
                    code = pool['reward_asset_code'],
                    issuer = pool['reward_asset_issuer']
                )
                if not self.is_on_blacklist(pool['pool_id']):
                    opportunity = Opportunity(
                        pool['pool_name'],
                        pool['pool_id'],
                        reward_asset,
                        pool['daily_reward_amount']
                    )       
                    opportunities.append(opportunity)
                else: 
                    print(pool['pool_id'])
        return opportunities
    
    def get_spreadsheet(self):
        rows = self.service_account.open_by_key(self.sheet_id)
        return rows.sheet1.get_all_records()
    

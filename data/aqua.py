from data.client import DataFeed
from models.opportunity import Opportunity, StellarAsset
from stellar_sdk import LiquidityPoolAsset, Asset
import json

import requests

class AquaFeed(DataFeed):

    aqua_url = "https://reward-api.aqua.network/api/rewards"

    def __init__(self):
        super().__init__()

    def pull_opportunities(self) -> list[Opportunity]:
        aqua_asset = StellarAsset(
            "token", 
            "AQUA",
            "GBNZILSTVQZ4R7IKQDGHYGY2QXL5QOFJYQMXPKWRRM5PAV7Y4M67AQUA"
        )
        opportunities = []
        all_aqua_pools = self.get_all_pages()
        for pool in all_aqua_pools:
            asset_a = Asset.native() if pool['market_key']['asset1_code'] == "XLM" and pool['market_key']['asset1_issuer'] == "" else Asset(pool['market_key']['asset1_code'],pool['market_key']['asset1_issuer'])
            asset_b = Asset.native() if pool['market_key']['asset2_code'] == "XLM" and pool['market_key']['asset2_issuer'] == "" else Asset(pool['market_key']['asset2_code'],pool['market_key']['asset2_issuer'])
            
            liquidity_pool = LiquidityPoolAsset(asset_a, asset_b) if LiquidityPoolAsset.is_valid_lexicographic_order(asset_a,asset_b) else LiquidityPoolAsset(asset_b, asset_a)
            if not self.is_on_blacklist(liquidity_pool.liquidity_pool_id):
                name = (asset_a.code + "-" + asset_b.code).lower()
                opportunity = Opportunity(name,liquidity_pool.liquidity_pool_id, aqua_asset, pool['daily_amm_reward'])
                opportunities.append(opportunity)
            else:
                print(liquidity_pool.liquidity_pool_id + " --- rejected")
        return opportunities

    def get_all_pages(self):
        pools = []

        page = 1

        page_results = self.pull_page(page)

        while page_results != None:
            for i in page_results:
                pools.append(i)
            page += 1
            page_results = self.pull_page(page)
            
        return pools

    def pull_page(self, number : int) -> dict:
        request = requests.get(f'{self.aqua_url}/?page={str(number)}').json()
        if "detail" in request:
            return None
        
        return request['results']
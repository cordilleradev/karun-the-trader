from stellar_sdk import Asset, Server
from models.nerd import KarunAI

usdc = Asset("USDC", "GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN")
server = Server('https://horizon.stellar.org')

class StellarAsset:
    def __init__(self, type : str, code : str = None, issuer : str = None):
        self.type = type
        self.code = code
        self.issuer = issuer

    def to_stellar_object(self) -> Asset:
        return Asset.native() if self.type == "native" else Asset(self.code,self.issuer)
    
    def get_amount_value(self, amount : float) -> float:
        path_query = server.strict_receive_paths(
            source = [usdc],
            destination_asset = self.to_stellar_object(),
            destination_amount = str(round(amount,7))
        ).call()
        if len(path_query['_embedded']['records']) > 0:
            return float(path_query['_embedded']['records'][0]['source_amount'])
            # return float(path_query['_embedded']['records'][0]['destination_amount'])
        return 0    
    
    def __eq__(self, other):
        return (other.type == self.type) if self.type == "native" else (other.code == self.code and other.issuer == self.issuer)

class Opportunity:
    def __init__(
        self,
        pool_name : str,
        pool_id : str,
        reward_asset : StellarAsset,
        reward_amount : float
    ):
        self.pool_name = pool_name
        self.pool_id = pool_id
        self.reward_asset = reward_asset
        self.reward_amount = reward_amount
        self.horizon = Server('https://horizon.stellar.org')

    # Fetch value of daily payments and pool
    def get_onchain_data(self):
        self.daily_payment_value = self.reward_asset.get_amount_value(self.reward_amount)
        self.pool_value = self.get_pool_value()
        print(f'fetched data for pool {self.pool_name} : {self.pool_id}')
        print(f'TVL: ${round(self.pool_value, 7)} with daily payments: ${round(self.daily_payment_value, 2)}')
        print()
    
    def get_pool_value(self) -> float:
        values = []

        liquidity_pool_info = server.liquidity_pools().liquidity_pool(self.pool_id).call()
        for reserve in liquidity_pool_info['reserves']:
            asset = StellarAsset(
                type = "native" if reserve['asset'] == "native" else "token",
                code = reserve['asset'].split(":")[0] if reserve['asset'] != "native" else None,
                issuer = reserve['asset'].split(":")[1] if reserve['asset'] != "native" else None,
            )
            value = asset.get_amount_value(float(reserve['amount']))
            values.append(value)
            print(f'{asset.type if asset.type == "native" else asset.code} : ${value}')
            
        share_eligibility_ratio = self.get_eligible_pool_share_ratio(self.pool_id, self.reward_asset, liquidity_pool_info)

        print(values)
        index = index_of_bigger(values)
        values[0 if index == 1 else 1 ] = values[index] if values[0 if index == 1 else 1] < values[index] * 0.1 else values[0 if index == 1 else 1]
        print(values)
        print(f"Share eligibility of {round(share_eligibility_ratio*100, 2)}%")

        return sum(values) * share_eligibility_ratio

    def get_eligible_pool_share_ratio(self, pool_id : str, asset : StellarAsset, pool_info : dict) -> float:
        for reserve_asset in pool_info['reserves']:
            if asset.type == "native" or reserve_asset['asset'] == f'{asset.code}:{asset.issuer}':
                return 1
        eligible_pool_share = 0
        total_pool_share = 0
        account_query = self.horizon.accounts().for_liquidity_pool(pool_id).limit(200)
        accounts = account_query.call()

        while(True):
            if len(accounts['_embedded']['records']) > 0:
                for account in accounts['_embedded']['records']:
                    total_pool_share += self.return_pool_shares(pool_id, account['balances'])
                    eligible_pool_share += self.return_pool_share_if_trustline(
                        pool_id,
                        asset,
                        account['balances']
                    )
                accounts = account_query.next()
            
            else : break
        return eligible_pool_share / total_pool_share

    def return_pool_share_if_trustline(self, pool_id : str, asset : StellarAsset, balances : dict) -> float:
        if self.has_trustline(
            asset,
            balances
        ):
            return self.return_pool_shares(pool_id, balances)
        return 0

    def has_trustline(self, asset : StellarAsset, balances : dict) -> bool:
        if asset.type == "native": 
            return True
        
        for balance in balances:
            if balance['asset_type'] in ['credit_alphanum12', 'credit_alphanum4']:
                if balance['asset_code'] == asset.code and balance['asset_issuer'] == asset.issuer:
                    return True
                
        return False

    def return_pool_shares(self, pool_id : str, balances : dict) -> float:
        for balance in balances:
            if balance['asset_type'] == "liquidity_pool_shares":
                if balance['liquidity_pool_id'] == pool_id:
                    return float(balance['balance'])
        return 0
    
    def equals(self, other): # TODO: TYPE HINT
        if isinstance(other, self.__class__):
            return self.pool_id == other.pool_id
        return False






class OpportunityEvaluator:
    karunAI = KarunAI()
    
    def __init__(self, opportunities : list[Opportunity], investment_size : float):
        self.opportunities = opportunities
        self.investment_size = investment_size
    
    def evaluate_opportunies(self) -> tuple[dict, float]:
        opportunity_tuples = []
        for opportunity in self.opportunities:
            opportunity_tuples.append(
                (
                    opportunity.pool_value,
                    opportunity.daily_payment_value,
                    opportunity.pool_id,
                )
            )
        print("calculating best split")
        output = self.karunAI.calculate_best_split(self.investment_size, opportunity_tuples)
        return output

def index_of_bigger(float_list : list[float]):
    return 0 if float_list[0] > float_list[1] else 1
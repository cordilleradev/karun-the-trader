from stellar_sdk import (
    Server,
    Keypair,
    Asset,
    TransactionBuilder,
    Network,
    LiquidityPoolAsset
)
from json import load
from models.opportunity import StellarAsset

wallet_config = load(open('config.json'))

class SwapOperation:
    def __init__(
        self,
        from_amount : float,
        from_asset : StellarAsset,
        to_asset : StellarAsset,
        to_address : str
    ):
        self.from_amount = from_amount
        self.from_asset = from_asset
        self.to_asset = to_asset
        self.to_address = to_address
    

class PoolPosition:
    def __init__(
        self,
        pool : LiquidityPoolAsset,
        total_shares : float,
        reserve_a : float,
        reserve_b : float,
    ):
        self.pool = pool
        self.total_shares = total_shares
        self.reserve_a = reserve_a
        self.reserve_b = reserve_b

class FarmerWallet:
    server = Server('https://horizon.stellar.org')
    max_swap_slippage = wallet_config['max-swap-slippage']
    max_withdraw_slippage = wallet_config['max-withdraw-slippage']

    def __init__(self, secret_key : str):
        self.keypair = Keypair.from_secret(secret_key)    
        self.public_key = self.keypair.public_key

    def run_payments(self, payments : list[tuple[str, float, StellarAsset]]):
        transactions = []
        op_count = 0
        account = self.server.load_account(self.public_key)

        transaction = TransactionBuilder(
            source_account = account,
            network_passphrase = Network.PUBLIC_NETWORK_PASSPHRASE,
            base_fee = 50000
        )
        
        for destination, amount, asset in payments:
            transaction.append_payment_op(
                destination=destination,
                asset=asset.to_stellar_object(),
                amount=str(amount)
            )

            op_count +=1 

            if op_count == 100:
                transaction.set_timeout(300)
                transaction = transaction.build()
                transaction.sign(self.keypair)
                transactions.append(transaction)

                account.increment_sequence_number()
                op_count = 0
                transaction = TransactionBuilder(
                    source_account = account,
                    network_passphrase = Network.PUBLIC_NETWORK_PASSPHRASE,
                    base_fee = 50000
                )
                
        if op_count > 0:
            transaction.set_timeout(300)
            transaction = transaction.build()
            transaction.sign(self.keypair)
            transactions.append(transaction)

        hashes = []
        for tx in transactions: 
            response = self.server.submit_transaction(tx)
            hashes.append(response['hash'])

        return hashes

    def swap_into_one(self, asset : StellarAsset) -> list[str]:
        balances = []

        account = self.server.load_account(self.public_key).raw_data
        for balance in account['balances']:
            if balance['asset_type'] in ['credit_alphanum12', 'credit_alphanum4']:
                is_native = balance['asset_type'] == "native"
                balance_asset = StellarAsset(
                    type = "native" if is_native else "token",
                    code = None if is_native else balance['asset_code'],
                    issuer = None if is_native else balance['asset_issuer']
                )
                print(balance_asset)
                print(asset)
                print(balance_asset == asset)
                if balance_asset != asset:
                    balances.append((balance_asset, float(balance['balance'])))
        
        swaperations = [
            SwapOperation(
                from_amount = balance,
                from_asset = balance_asset,
                to_asset = asset, 
                to_address = self.public_key
            ) for balance_asset, balance in balances if not balance_asset.type == "native"
        ]
        hashes = self.run_swaps(swaperations)

        return hashes
            
    def get_asset_positions(self) -> list[tuple[float,StellarAsset]]:
        balances = []
        account = self.server.load_account(self.public_key).raw_data
        for balance in account['balances']:
            if balance['asset_type'] in ['native', 'credit_alphanum12', 'credit_alphanum4']:
                is_native = balance['asset_type'] == "native"
                balances.append(
                    (
                        float(balance['balance']),
                        StellarAsset(
                            type="native" if is_native else "token",
                            code= None if is_native else balance['asset_code'],
                            issuer= None if is_native else balance['asset_issuer'],
                        )
                    )
                )
        return balances
    def get_pool_positions(self) -> list[PoolPosition]:
        positions = []
        account = self.server.load_account(self.public_key).raw_data
        for balance in account['balances']:
            if balance['asset_type'] == "liquidity_pool_shares":
                pool_info = self.server.liquidity_pools().liquidity_pool(balance['liquidity_pool_id']).call()
                total_shares = float(pool_info['total_shares'])
                my_total_shares = float(balance['balance']) 
                my_share_ratio = my_total_shares / total_shares
                bal_asset_a = round(float(pool_info['reserves'][0]['amount']) * my_share_ratio,7)
                bal_asset_b = round(float(pool_info['reserves'][1]['amount']) * my_share_ratio,7)
                positions.append(
                    PoolPosition(
                        LiquidityPoolAsset(
                            Asset.native() if pool_info['reserves'][0]['asset'] == "native" else Asset(
                                pool_info['reserves'][0]['asset'].split(":")[0],
                                pool_info['reserves'][0]['asset'].split(":")[1]
                            ),
                            Asset.native() if pool_info['reserves'][1]['asset'] == "native" else Asset(
                                pool_info['reserves'][1]['asset'].split(":")[0],
                                pool_info['reserves'][1]['asset'].split(":")[1]
                            )),
                        my_total_shares,
                        bal_asset_a,
                        bal_asset_b
                    )
                )
        return positions
                                    
    def run_withdraws(self, operations : list[PoolPosition]):
        transactions = []
        op_count = 0
        account = self.server.load_account(self.public_key)

        transaction = TransactionBuilder(
            source_account = account,
            network_passphrase = Network.PUBLIC_NETWORK_PASSPHRASE,
            base_fee = 50000
        )

        for operation in operations:
            if operation.total_shares > 0:
                transaction.append_liquidity_pool_withdraw_op(
                    liquidity_pool_id = operation.pool.liquidity_pool_id,
                    amount = str(operation.total_shares),
                    min_amount_a = str(
                        round(operation.reserve_a * (1-self.max_withdraw_slippage), 7)
                    ),
                    min_amount_b = str(
                        round(operation.reserve_b * (1-self.max_withdraw_slippage), 7)
                    )
                )
                transaction.append_change_trust_op(
                    asset = operation.pool,
                    limit = 0
                )
                op_count +=2

            if op_count == 100:
                transaction.set_timeout(300)
                transaction = transaction.build()
                transaction.sign(self.keypair)
                transactions.append(transaction)

                account.increment_sequence_number()
                op_count = 0
                transaction = TransactionBuilder(
                    source_account = account,
                    network_passphrase = Network.PUBLIC_NETWORK_PASSPHRASE,
                    base_fee = 50000
                )
                
        if op_count > 0:
            transaction.set_timeout(300)
            transaction = transaction.build()
            transaction.sign(self.keypair)
            transactions.append(transaction)
        hashes = []
        for tx in transactions: 
            response = self.server.submit_transaction(tx)
            hashes.append(response['hash'])

        return hashes



    # Run a list of swap operations
    def run_swaps(self, operations : list[SwapOperation]):
        transactions = []
        op_count = 0
        account = self.server.load_account(self.public_key)

        transaction = TransactionBuilder(
            source_account = account,
            network_passphrase = Network.PUBLIC_NETWORK_PASSPHRASE,
            base_fee = 50000
        )
        
        for operation in operations:
            path, destination_amount = self.get_best_path(operation)
            if destination_amount > 0:
                transaction.append_path_payment_strict_send_op(
                    destination = operation.to_address,
                    send_asset = operation.from_asset.to_stellar_object(),
                    send_amount = str(operation.from_amount),
                    dest_asset = operation.to_asset.to_stellar_object(),
                    dest_min = str(
                        round(
                            (1 - self.max_swap_slippage) * destination_amount, 7 
                        )
                    ),
                    path = path
                )
                op_count +=1 

            if op_count == 100:
                transaction.set_timeout(300)
                transaction = transaction.build()
                transaction.sign(self.keypair)
                transactions.append(transaction)

                account.increment_sequence_number()
                op_count = 0
                transaction = TransactionBuilder(
                    source_account = account,
                    network_passphrase = Network.PUBLIC_NETWORK_PASSPHRASE,
                    base_fee = 50000
                )
                
        if op_count > 0:
            transaction.set_timeout(300)
            transaction = transaction.build()
            transaction.sign(self.keypair)
            transactions.append(transaction)

        hashes = []
        for tx in transactions: 
            response = self.server.submit_transaction(tx)
            hashes.append(response['hash'])

        return hashes

    
    def get_best_path(self, swap : SwapOperation):
        if swap.from_amount > 0:
            path_query = self.server.strict_send_paths(
                source_asset = swap.from_asset.to_stellar_object(),
                source_amount = f'{swap.from_amount:f}',
                destination = [swap.to_asset.to_stellar_object()]
            ).call()

            if len(path_query['_embedded']['records']) > 0:
                path = []
                for asset in path_query['_embedded']['records'][0]['path']:
                    asset_obj = None
                    if asset['asset_type'] == "native":
                        asset_obj = Asset.native()
                    else:
                        asset_obj = Asset(asset['asset_code'], asset['asset_issuer']) 
                    path.append(asset_obj)
                return path, float(path_query['_embedded']['records'][0]['destination_amount'])

        return [], 0


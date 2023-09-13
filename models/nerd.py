from collections import Counter

class KarunAI:
    
    def calculate_best_split(self, investment_size : float,opportunities : list[tuple] = []) -> tuple[dict, float]:
        opportunities = merge_pools(opportunities)
        names = [n for _, _, n in opportunities]
        opportunities = [(p, r) for p, r, _ in opportunities]
        num_opportunities = len(opportunities)
        
        dp = [[0] * (investment_size + 1) for _ in range(num_opportunities + 1)]
        parent = [[None] * (investment_size + 1) for _ in range(num_opportunities + 1)]

        for i in range(num_opportunities + 1):
            dp[i][0] = 0
            parent[i][0] = 0

        for i in range(investment_size + 1):
            dp[0][i] = 0
            parent[0][i] = 0
        

        for i in range(1, num_opportunities + 1):
            print(f"Analyzing opportunity {i}/{num_opportunities}")
            for j in range(1, investment_size + 1):
                m, mk = 0, None
                for k in range(0, j+1):
                    cand = dp[i-1][j-k] + returns(*opportunities[i-1], k)
                    if cand > m:
                        m = cand
                        mk = k
                dp[i][j] = m
                parent[i][j] = mk

        i = num_opportunities
        j = investment_size

        allocations = []
        while j >= 0 and i > 0:
            allocations = [parent[i][j]] + allocations
            j -= parent[i][j]
            i -= 1
        allocations = {names[i]: allocations[i] for i in range(len(opportunities))}

        return allocations, dp[-1][-1]

def merge_pools(opps):
        rewards = Counter()
        for ind, (pool, reward, name) in enumerate(opps):
            rewards[(name, pool)] += reward
        return [(p, r, n) for (n, p), r in rewards.items()]


def returns(p : float, r : float, x : float) -> float:
    return x / (p + x) * r



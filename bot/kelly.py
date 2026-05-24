"""
Kelly Criterion position sizing for Polymarket trades.
Calculates optimal bet fraction based on edge and odds.
"""


class KellySizer:
    """
    Kelly Criterion: f* = p - (1-p)/b

    Where:
        p = probability of winning (from Markov model)
        b = net odds received on the bet (payout ratio)
        f* = fraction of bankroll to bet

    For Polymarket:
        If you buy YES at price q, and it resolves YES:
            payout = 1.0 per share (you paid q)
            profit = 1 - q
            b = (1 - q) / q

        If you buy NO at price (1-q), and it resolves NO:
            payout = 1.0 per share (you paid 1-q)
            profit = q
            b = q / (1 - q)
    """

    def __init__(self, max_fraction: float = 0.25, min_bet: float = 1.0, max_bet: float = 50.0):
        """
        Args:
            max_fraction: Maximum Kelly fraction (cap to reduce variance).
                          0.25 = quarter-Kelly, conservative.
            min_bet: Minimum bet size in dollars.
            max_bet: Maximum bet size in dollars.
        """
        self.max_fraction = max_fraction
        self.min_bet = min_bet
        self.max_bet = max_bet

    def calculate_kelly_fraction(self, p: float, q: float) -> float:
        """
        Calculate Kelly fraction for a YES trade.

        Args:
            p: Model probability of outcome (from Markov)
            q: Market price (what you pay per share)

        Returns:
            Kelly fraction (0.0 to max_fraction)
        """
        if q <= 0 or q >= 1:
            return 0.0
        if p <= 0 or p >= 1:
            return 0.0

        # Net odds: how much you win per dollar risked
        b = (1 - q) / q

        # Kelly formula
        f_star = p - (1 - p) / b

        # Never bet negative (no edge)
        if f_star <= 0:
            return 0.0

        # Cap at max_fraction (fractional Kelly for safety)
        return min(f_star, self.max_fraction)

    def calculate_bet_size(self, p: float, q: float, bankroll: float) -> float:
        """
        Calculate actual dollar bet size.

        Args:
            p: Model probability
            q: Market price
            bankroll: Current bankroll in dollars

        Returns:
            Bet size in dollars (0.0 if no trade)
        """
        fraction = self.calculate_kelly_fraction(p, q)

        if fraction <= 0:
            return 0.0

        bet = bankroll * fraction

        # Apply min/max constraints
        if bet < self.min_bet:
            # If Kelly says bet less than minimum, skip trade
            return 0.0

        bet = min(bet, self.max_bet)
        bet = min(bet, bankroll)  # Never bet more than you have

        return round(bet, 2)

    def calculate_expected_value(self, p: float, q: float, bet_size: float) -> float:
        """
        Calculate expected value of a trade.

        Args:
            p: Model probability
            q: Market price
            bet_size: Dollar amount to bet

        Returns:
            Expected dollar profit/loss
        """
        if bet_size <= 0:
            return 0.0

        # Shares purchased
        shares = bet_size / q

        # EV = p * profit - (1-p) * loss
        profit_if_win = shares * (1 - q)  # = shares - bet_size
        loss_if_lose = bet_size

        ev = p * profit_if_win - (1 - p) * loss_if_lose
        return round(ev, 4)

    def get_edge(self, p: float, q: float) -> float:
        """
        Calculate the edge (gap between model and market).

        Args:
            p: Model probability
            q: Market price

        Returns:
            Edge as decimal (0.05 = 5% edge)
        """
        return p - q

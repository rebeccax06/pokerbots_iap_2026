'''
Fast hand evaluator for 7-card poker hands.
Uses a simplified approach suitable for Monte Carlo simulations.
'''

from itertools import combinations
from functools import lru_cache


# Card representation: "2h" = 2 of hearts, "As" = Ace of spades
RANKS = "23456789TJQKA"
SUITS = "cdhs"  # clubs, diamonds, hearts, spades

RANK_VALUES = {rank: i for i, rank in enumerate(RANKS)}


@lru_cache(maxsize=100000)
def evaluate_hand(cards_tuple):
    """
    Evaluate the best 5-card poker hand from up to 7 cards.
    
    Args:
        cards_tuple: Tuple of card strings (e.g., ("As", "Kh", "Qd", "Jc", "Ts"))
    
    Returns:
        Integer score where higher is better
    """
    cards = list(cards_tuple)
    
    if len(cards) < 5:
        return 0  # Invalid hand
    
    best_score = 0
    
    # Try all 5-card combinations
    for hand in combinations(cards, 5):
        score = evaluate_5card_hand(hand)
        if score > best_score:
            best_score = score
    
    return best_score


def evaluate_5card_hand(hand):
    """
    Evaluate exactly 5 cards and return a score.
    
    Hand rankings (higher is better):
    - Straight Flush: 8 * 10^6 + high_card
    - Four of a Kind: 7 * 10^6 + quad_rank * 13 + kicker
    - Full House: 6 * 10^6 + trips_rank * 13 + pair_rank
    - Flush: 5 * 10^6 + card values
    - Straight: 4 * 10^6 + high_card
    - Three of a Kind: 3 * 10^6 + trips_rank * 169 + kicker1 * 13 + kicker2
    - Two Pair: 2 * 10^6 + high_pair * 169 + low_pair * 13 + kicker
    - One Pair: 1 * 10^6 + pair_rank * 2197 + kicker1 * 169 + kicker2 * 13 + kicker3
    - High Card: card values
    """
    ranks = [RANK_VALUES[card[0]] for card in hand]
    suits = [card[1] for card in hand]
    
    ranks.sort(reverse=True)
    
    # Check for flush
    is_flush = len(set(suits)) == 1
    
    # Check for straight
    is_straight = False
    straight_high = 0
    
    # Normal straight
    if ranks[0] - ranks[4] == 4 and len(set(ranks)) == 5:
        is_straight = True
        straight_high = ranks[0]
    # Wheel (A-2-3-4-5)
    elif ranks == [12, 3, 2, 1, 0]:  # A-5-4-3-2
        is_straight = True
        straight_high = 3  # 5-high straight
    
    # Straight Flush
    if is_straight and is_flush:
        return 8_000_000 + straight_high
    
    # Count rank frequencies
    rank_counts = {}
    for rank in ranks:
        rank_counts[rank] = rank_counts.get(rank, 0) + 1
    
    counts = sorted(rank_counts.items(), key=lambda x: (x[1], x[0]), reverse=True)
    
    # Four of a Kind
    if counts[0][1] == 4:
        return 7_000_000 + counts[0][0] * 13 + counts[1][0]
    
    # Full House
    if counts[0][1] == 3 and counts[1][1] == 2:
        return 6_000_000 + counts[0][0] * 13 + counts[1][0]
    
    # Flush
    if is_flush:
        return 5_000_000 + ranks[0] * 28561 + ranks[1] * 2197 + ranks[2] * 169 + ranks[3] * 13 + ranks[4]
    
    # Straight
    if is_straight:
        return 4_000_000 + straight_high
    
    # Three of a Kind
    if counts[0][1] == 3:
        kickers = sorted([c[0] for c in counts[1:]], reverse=True)
        return 3_000_000 + counts[0][0] * 169 + kickers[0] * 13 + kickers[1]
    
    # Two Pair
    if counts[0][1] == 2 and counts[1][1] == 2:
        return 2_000_000 + counts[0][0] * 169 + counts[1][0] * 13 + counts[2][0]
    
    # One Pair
    if counts[0][1] == 2:
        kickers = sorted([c[0] for c in counts[1:]], reverse=True)
        return 1_000_000 + counts[0][0] * 2197 + kickers[0] * 169 + kickers[1] * 13 + kickers[2]
    
    # High Card
    return ranks[0] * 28561 + ranks[1] * 2197 + ranks[2] * 169 + ranks[3] * 13 + ranks[4]


def get_hand_strength_category(cards):
    """
    Returns a coarse category for the hand strength (0-8).
    Used for bucketing in MCCFR.
    
    0: High Card
    1: Pair
    2: Two Pair
    3: Three of a Kind
    4: Straight
    5: Flush
    6: Full House
    7: Four of a Kind
    8: Straight Flush
    """
    if not cards or len(cards) < 5:
        return 0
    
    score = evaluate_hand(tuple(cards))
    
    if score >= 8_000_000:
        return 8
    elif score >= 7_000_000:
        return 7
    elif score >= 6_000_000:
        return 6
    elif score >= 5_000_000:
        return 5
    elif score >= 4_000_000:
        return 4
    elif score >= 3_000_000:
        return 3
    elif score >= 2_000_000:
        return 2
    elif score >= 1_000_000:
        return 1
    else:
        return 0


def compare_hands(cards1, cards2):
    """
    Compare two hands and return 1 if cards1 wins, -1 if cards2 wins, 0 for tie.
    """
    score1 = evaluate_hand(tuple(cards1))
    score2 = evaluate_hand(tuple(cards2))
    
    if score1 > score2:
        return 1
    elif score1 < score2:
        return -1
    else:
        return 0


def get_hand_percentile(cards):
    """
    Returns a rough percentile (0-100) of hand strength.
    Useful for bucketing.
    """
    if not cards or len(cards) < 5:
        return 0
    
    score = evaluate_hand(tuple(cards))
    category = get_hand_strength_category(cards)
    
    # Rough percentile mapping based on hand category
    if category == 8:  # Straight Flush
        return 99
    elif category == 7:  # Quads
        return 97
    elif category == 6:  # Full House
        return 92
    elif category == 5:  # Flush
        return 82
    elif category == 4:  # Straight
        return 70
    elif category == 3:  # Trips
        return 55
    elif category == 2:  # Two Pair
        return 35
    elif category == 1:  # Pair
        # Within pair, differentiate by score
        pair_strength = (score - 1_000_000) / 2_000_000 * 100
        return min(20, max(5, pair_strength))
    else:  # High Card
        return 2


if __name__ == "__main__":
    # Quick tests
    test_hands = [
        ["As", "Ks", "Qs", "Js", "Ts"],  # Royal Flush
        ["9h", "8h", "7h", "6h", "5h"],  # Straight Flush
        ["Ah", "Ad", "Ac", "As", "Kh"],  # Four of a Kind (impossible but for testing)
        ["Kh", "Kd", "Kc", "Qh", "Qd"],  # Full House
        ["Ah", "Kh", "Qh", "Jh", "9h"],  # Flush
        ["9h", "8d", "7c", "6s", "5h"],  # Straight
        ["7h", "7d", "7c", "Ah", "Kh"],  # Three of a Kind
        ["Jh", "Jd", "9c", "9s", "Ah"],  # Two Pair
        ["Qh", "Qd", "9c", "7s", "5h"],  # One Pair
        ["Ah", "Kd", "Qc", "Js", "9h"],  # High Card
    ]
    
    for hand in test_hands:
        score = evaluate_5card_hand(hand)
        category = get_hand_strength_category(hand)
        print(f"{hand}: Score={score}, Category={category}")


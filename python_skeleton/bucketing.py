'''
Bucketing system for information set abstraction in MCCFR.
Maps game states to coarse buckets to reduce memory usage.
'''

from hand_evaluator import evaluate_hand, get_hand_strength_category, RANK_VALUES


def get_preflop_bucket(hole_cards):
    """
    Bucket for 3-card preflop holdings.
    
    Returns:
        String bucket identifier
    """
    if len(hole_cards) != 3:
        return "invalid"
    
    ranks = sorted([RANK_VALUES[card[0]] for card in hole_cards], reverse=True)
    suits = [card[1] for card in hole_cards]
    
    # Check for suited cards
    suited_count = max(suits.count(s) for s in set(suits))
    is_suited = suited_count >= 2
    is_trips = ranks[0] == ranks[1] == ranks[2]
    is_pair = ranks[0] == ranks[1] or ranks[1] == ranks[2]
    
    # Coarse bucketing based on high card, pairs, and suitedness
    high_rank = ranks[0]
    
    if is_trips:
        bucket = f"trips_{high_rank}"
    elif is_pair:
        pair_rank = ranks[0] if ranks[0] == ranks[1] else ranks[1]
        kicker = ranks[2] if ranks[0] == ranks[1] else ranks[0]
        # Group pairs into buckets
        if pair_rank >= 10:  # JJ+
            bucket = "high_pair"
        elif pair_rank >= 7:  # 88-TT
            bucket = "mid_pair"
        else:
            bucket = "low_pair"
    else:
        # No pair - categorize by high card and connectivity
        gap = ranks[0] - ranks[2]
        
        if high_rank >= 11:  # Queen or better high
            if is_suited:
                bucket = "high_suited"
            else:
                bucket = "high_offsuit"
        elif high_rank >= 8:  # 9 to Jack high
            if is_suited:
                bucket = "mid_suited"
            else:
                bucket = "mid_offsuit"
        else:
            bucket = "low"
    
    return bucket


def get_board_texture(board_cards):
    """
    Categorize board texture for bucketing.
    
    Returns:
        String representing board texture
    """
    if not board_cards:
        return "empty"
    
    ranks = [RANK_VALUES[card[0]] for card in board_cards]
    suits = [card[1] for card in board_cards]
    
    # Check for pairs on board
    rank_counts = {}
    for rank in ranks:
        rank_counts[rank] = rank_counts.get(rank, 0) + 1
    
    has_pair = any(count >= 2 for count in rank_counts.values())
    has_trips = any(count >= 3 for count in rank_counts.values())
    
    # Check for flush draw (3+ of same suit)
    suit_counts = {}
    for suit in suits:
        suit_counts[suit] = suit_counts.get(suit, 0) + 1
    
    flush_draw = any(count >= 3 for count in suit_counts.values())
    
    # Check for straight potential
    if len(ranks) >= 3:
        sorted_ranks = sorted(set(ranks), reverse=True)
        max_gap = 0
        if len(sorted_ranks) >= 2:
            for i in range(len(sorted_ranks) - 1):
                gap = sorted_ranks[i] - sorted_ranks[i + 1]
                if gap > max_gap:
                    max_gap = gap
        
        connected = max_gap <= 2 if len(sorted_ranks) >= 3 else False
    else:
        connected = False
    
    # Build texture string
    texture = []
    
    if has_trips:
        texture.append("trips")
    elif has_pair:
        texture.append("paired")
    else:
        texture.append("rainbow")
    
    if flush_draw:
        texture.append("flush")
    
    if connected:
        texture.append("connected")
    
    return "_".join(texture) if texture else "dry"


def get_postflop_bucket(hole_cards, board_cards, discarded_cards=None):
    """
    Bucket for postflop situations.
    Combines hand strength and board texture.
    
    Args:
        hole_cards: Player's remaining hole cards (2 after discard, or 3 before)
        board_cards: Community cards
        discarded_cards: Public discarded cards (optional)
    
    Returns:
        String bucket identifier
    """
    # Combine all available cards for hand evaluation
    all_cards = hole_cards + board_cards
    if discarded_cards:
        all_cards += discarded_cards
    
    if len(all_cards) < 5:
        # Not enough cards for a full evaluation
        return get_preflop_bucket(hole_cards)
    
    # Get hand strength category
    hand_category = get_hand_strength_category(all_cards)
    
    # Get board texture
    texture = get_board_texture(board_cards)
    
    # Combine into bucket
    bucket = f"cat{hand_category}_{texture}"
    
    return bucket


def get_discard_bucket(hole_cards, board_cards):
    """
    Special bucketing for discard decision.
    Evaluates potential of each card to keep.
    
    Returns:
        String bucket representing the relative strength of the 3 cards
    """
    if len(hole_cards) != 3:
        return "invalid"
    
    # Evaluate strength if we keep each pair of cards
    strengths = []
    for discard_idx in range(3):
        kept_cards = [hole_cards[i] for i in range(3) if i != discard_idx]
        all_cards = kept_cards + board_cards
        
        if len(all_cards) >= 5:
            strength = evaluate_hand(tuple(all_cards))
        else:
            # Just use kept cards value as proxy
            strength = sum(RANK_VALUES[card[0]] for card in kept_cards)
        
        strengths.append(strength)
    
    # Determine which card is weakest
    min_strength = min(strengths)
    max_strength = max(strengths)
    
    # Bucket based on strength gap
    strength_gap = max_strength - min_strength
    
    if strength_gap < 10000:
        return "close_decision"
    else:
        return "clear_discard"


def get_infoset_key(player_id, hole_cards, board_cards, discarded_by_us, 
                    discarded_by_opp, street, betting_history, position):
    """
    Generate a unique information set key for a game state from a player's perspective.
    
    Args:
        player_id: 0 or 1
        hole_cards: List of player's current hole cards
        board_cards: List of community cards
        discarded_by_us: Card we discarded (or None)
        discarded_by_opp: Card opponent discarded (or None)  
        street: 0 (preflop), 2 (flop), 3 (post-discard), 4 (turn), 5 (river), 6 (showdown)
        betting_history: List of action codes for current street
        position: True if button, False if out of position
    
    Returns:
        String representing the information set
    """
    # Determine bucketing strategy based on street
    if street == 0:
        # Preflop
        bucket = get_preflop_bucket(hole_cards)
    elif street in [2, 3]:
        # Flop or discard round
        if len(hole_cards) == 3:
            bucket = get_discard_bucket(hole_cards, board_cards)
        else:
            # After discard
            discarded = [discarded_by_us] if discarded_by_us else []
            if discarded_by_opp:
                discarded.append(discarded_by_opp)
            bucket = get_postflop_bucket(hole_cards, board_cards, discarded)
    else:
        # Turn or river
        discarded = []
        if discarded_by_us:
            discarded.append(discarded_by_us)
        if discarded_by_opp:
            discarded.append(discarded_by_opp)
        bucket = get_postflop_bucket(hole_cards, board_cards, discarded)
    
    # Encode betting history as string
    bet_history_str = "".join(betting_history) if betting_history else "none"
    
    # Position indicator
    pos_str = "btn" if position else "oop"
    
    # Combine all components
    infoset = f"s{street}_{pos_str}_{bucket}_{bet_history_str}"
    
    return infoset


if __name__ == "__main__":
    # Quick tests
    print("Testing preflop bucketing:")
    print(get_preflop_bucket(["As", "Ah", "Kd"]))  # High pair
    print(get_preflop_bucket(["7s", "6s", "5s"]))  # Mid suited
    print(get_preflop_bucket(["2d", "3h", "7c"]))  # Low
    
    print("\nTesting board texture:")
    print(get_board_texture(["Ah", "Kh", "Qh"]))  # Flush draw, connected
    print(get_board_texture(["7s", "7d", "2c"]))  # Paired
    
    print("\nTesting postflop bucketing:")
    print(get_postflop_bucket(["As", "Ah"], ["Kh", "Qh", "Jh", "Th"]))  # Strong hand
    print(get_postflop_bucket(["2s", "3h"], ["Kh", "Qd", "Jc"]))  # Weak hand



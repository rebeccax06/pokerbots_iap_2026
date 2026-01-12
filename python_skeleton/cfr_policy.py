'''
Runtime policy module that loads trained MCCFR strategy and makes decisions.
Used by the Player bot during actual gameplay.
'''

import os
import pickle
import random
from collections import defaultdict
from bucketing import get_infoset_key
from hand_evaluator import evaluate_hand, compare_hands, RANK_VALUES
from game_abstraction import (
    ACTION_FOLD, ACTION_CHECK_CALL, ACTION_BET_33, ACTION_BET_66,
    ACTION_BET_POT, ACTION_ALL_IN, ACTION_DISCARD_0, ACTION_DISCARD_1, ACTION_DISCARD_2
)
from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction, DiscardAction
from skeleton.states import STARTING_STACK, BIG_BLIND


class CFRPolicy:
    """
    Loads and queries a trained MCCFR strategy for decision making.
    """
    
    def __init__(self, strategy_path=None):
        """
        Initialize policy.
        
        Args:
            strategy_path: Path to saved strategy file (pickle). If None, uses fallback heuristic.
        """
        self.strategy_sum = defaultdict(lambda: defaultdict(float))
        self.has_strategy = False
        
        if strategy_path and os.path.exists(strategy_path):
            self.load_strategy(strategy_path)
    
    def load_strategy(self, filepath):
        """Load strategy from file."""
        try:
            with open(filepath, 'rb') as f:
                data = pickle.load(f)
            
            for infoset, actions in data['strategy_sum'].items():
                for action, value in actions.items():
                    self.strategy_sum[infoset][action] = value
            
            self.has_strategy = True
            print(f"Loaded strategy with {len(self.strategy_sum)} infosets")
        except Exception as e:
            print(f"Warning: Failed to load strategy from {filepath}: {e}")
            self.has_strategy = False
    
    def get_strategy(self, infoset, legal_actions):
        """
        Get strategy for an information set.
        
        Args:
            infoset: Information set key
            legal_actions: List of legal action codes
        
        Returns:
            Dict mapping action -> probability
        """
        if not legal_actions:
            return {}
        
        strategy_totals = self.strategy_sum.get(infoset, {})
        total = sum(strategy_totals.get(action, 0.0) for action in legal_actions)
        
        if total <= 0:
            # No data for this infoset, use uniform
            prob = 1.0 / len(legal_actions)
            return {action: prob for action in legal_actions}
        
        # Normalize
        strategy = {}
        for action in legal_actions:
            strategy[action] = strategy_totals.get(action, 0.0) / total
        
        return strategy
    
    def sample_action(self, strategy):
        """Sample action from strategy."""
        if not strategy:
            return None
        
        actions = list(strategy.keys())
        probs = [strategy[a] for a in actions]
        
        return random.choices(actions, weights=probs)[0]
    
    def get_discard_decision(self, my_cards, board_cards, player_id, position):
        """
        Decide which card to discard.
        
        Args:
            my_cards: List of 3 hole cards
            board_cards: List of board cards
            player_id: 0 or 1
            position: True if button
        
        Returns:
            Index of card to discard (0, 1, or 2)
        """
        if len(my_cards) != 3:
            return 0
        
        # Build infoset
        infoset = get_infoset_key(
            player_id=player_id,
            hole_cards=my_cards,
            board_cards=board_cards,
            discarded_by_us=None,
            discarded_by_opp=None,
            street=2,  # Flop/discard street
            betting_history=[],
            position=position
        )
        
        legal_actions = [ACTION_DISCARD_0, ACTION_DISCARD_1, ACTION_DISCARD_2]
        
        if self.has_strategy:
            strategy = self.get_strategy(infoset, legal_actions)
            action = self.sample_action(strategy)
            return action - ACTION_DISCARD_0
        else:
            # Fallback: discard the card that results in weakest hand
            return self._heuristic_discard(my_cards, board_cards)
    
    def _heuristic_discard(self, my_cards, board_cards):
        """
        Heuristic discard: keep the two cards that make the best hand with the board.
        """
        best_discard = 0
        best_strength = -1
        
        for discard_idx in range(3):
            kept_cards = [my_cards[i] for i in range(3) if i != discard_idx]
            all_cards = kept_cards + board_cards
            
            if len(all_cards) >= 5:
                strength = evaluate_hand(tuple(all_cards))
            else:
                # Not enough cards, just use rank sum
                strength = sum(RANK_VALUES[card[0]] for card in kept_cards)
            
            if strength > best_strength:
                best_strength = strength
                best_discard = discard_idx
        
        return best_discard
    
    def get_betting_decision(self, my_cards, board_cards, discarded_by_us, discarded_by_opp,
                             street, my_pip, opp_pip, my_stack, opp_stack, pot,
                             legal_actions, player_id, position, betting_history):
        """
        Decide betting action.
        
        Args:
            my_cards: List of my hole cards
            board_cards: List of board cards
            discarded_by_us: Card we discarded (or None)
            discarded_by_opp: Card opponent discarded (or None)
            street: Current street
            my_pip: My contribution this street
            opp_pip: Opponent contribution this street
            my_stack: My remaining stack
            opp_stack: Opponent remaining stack
            pot: Total pot size
            legal_actions: Set of legal engine actions
            player_id: 0 or 1
            position: True if button
            betting_history: List of action strings this street
        
        Returns:
            Engine action object (FoldAction, CallAction, CheckAction, RaiseAction)
        """
        # Build infoset
        infoset = get_infoset_key(
            player_id=player_id,
            hole_cards=my_cards,
            board_cards=board_cards,
            discarded_by_us=discarded_by_us,
            discarded_by_opp=discarded_by_opp,
            street=street,
            betting_history=betting_history,
            position=position
        )
        
        # Map engine actions to abstract actions
        abstract_actions = self._map_legal_actions(
            legal_actions, my_pip, opp_pip, my_stack, pot
        )
        
        if not abstract_actions:
            # Fallback
            if CheckAction in legal_actions:
                return CheckAction()
            elif CallAction in legal_actions:
                return CallAction()
            else:
                return FoldAction()
        
        # Get strategy
        if self.has_strategy:
            strategy = self.get_strategy(infoset, abstract_actions)
            action = self.sample_action(strategy)
        else:
            # Fallback heuristic
            action = self._heuristic_betting(
                my_cards, board_cards, discarded_by_us, discarded_by_opp,
                my_pip, opp_pip, my_stack, pot, abstract_actions
            )
        
        # Convert abstract action to engine action
        return self._abstract_to_engine_action(
            action, legal_actions, my_pip, opp_pip, my_stack, pot
        )
    
    def _map_legal_actions(self, legal_actions, my_pip, opp_pip, my_stack, pot):
        """
        Map engine legal actions to abstract action codes.
        """
        abstract = []
        
        facing_bet = opp_pip > my_pip
        amount_to_call = opp_pip - my_pip
        
        if FoldAction in legal_actions:
            abstract.append(ACTION_FOLD)
        
        if CheckAction in legal_actions or CallAction in legal_actions:
            abstract.append(ACTION_CHECK_CALL)
        
        if RaiseAction in legal_actions:
            # Check which bet sizes are feasible
            remaining = my_stack - amount_to_call if facing_bet else my_stack
            current_pot = pot + amount_to_call if facing_bet else pot
            
            if remaining > 0:
                if remaining >= current_pot * 0.33:
                    abstract.append(ACTION_BET_33)
                if remaining >= current_pot * 0.66:
                    abstract.append(ACTION_BET_66)
                if remaining >= current_pot:
                    abstract.append(ACTION_BET_POT)
                abstract.append(ACTION_ALL_IN)
        
        return abstract
    
    def _abstract_to_engine_action(self, action, legal_actions, my_pip, opp_pip, my_stack, pot):
        """
        Convert abstract action code to engine action object.
        """
        if action == ACTION_FOLD:
            return FoldAction()
        
        if action == ACTION_CHECK_CALL:
            if CheckAction in legal_actions:
                return CheckAction()
            else:
                return CallAction()
        
        # Betting/raising actions
        if action in [ACTION_BET_33, ACTION_BET_66, ACTION_BET_POT, ACTION_ALL_IN]:
            if RaiseAction not in legal_actions:
                # Can't raise, fall back to call or check
                if CheckAction in legal_actions:
                    return CheckAction()
                else:
                    return CallAction()
            
            # Compute bet size
            facing_bet = opp_pip > my_pip
            amount_to_call = opp_pip - my_pip if facing_bet else 0
            current_pot = pot + amount_to_call
            
            if action == ACTION_BET_33:
                bet_size = int(current_pot * 0.33)
            elif action == ACTION_BET_66:
                bet_size = int(current_pot * 0.66)
            elif action == ACTION_BET_POT:
                bet_size = current_pot
            else:  # ALL_IN
                bet_size = my_stack - amount_to_call
            
            # Ensure bet is in legal range
            from skeleton.states import RoundState
            # We don't have RoundState here, so approximate
            min_raise = amount_to_call + max(amount_to_call, BIG_BLIND)
            max_raise = my_stack
            
            total_contribution = my_pip + amount_to_call + bet_size
            total_contribution = max(my_pip + min_raise, min(total_contribution, my_pip + max_raise))
            
            return RaiseAction(total_contribution)
        
        # Default fallback
        if CheckAction in legal_actions:
            return CheckAction()
        elif CallAction in legal_actions:
            return CallAction()
        else:
            return FoldAction()
    
    def _heuristic_betting(self, my_cards, board_cards, discarded_by_us, discarded_by_opp,
                           my_pip, opp_pip, my_stack, pot, abstract_actions):
        """
        Simple heuristic betting based on hand strength and pot odds.
        """
        # Estimate hand strength via Monte Carlo sampling
        equity = self._estimate_equity(my_cards, board_cards, discarded_by_us, 
                                       discarded_by_opp, num_samples=50)
        
        facing_bet = opp_pip > my_pip
        amount_to_call = opp_pip - my_pip if facing_bet else 0
        
        # Simple strategy based on equity
        if facing_bet:
            pot_odds = amount_to_call / (pot + amount_to_call)
            
            if equity < pot_odds * 0.8:
                # Bad pot odds, fold
                if ACTION_FOLD in abstract_actions:
                    return ACTION_FOLD
                return ACTION_CHECK_CALL
            elif equity > 0.65:
                # Strong hand, raise
                if ACTION_BET_POT in abstract_actions:
                    return ACTION_BET_POT
                return ACTION_CHECK_CALL
            else:
                # Marginal, call
                return ACTION_CHECK_CALL
        else:
            # No bet facing
            if equity > 0.6:
                # Strong hand, bet
                if ACTION_BET_66 in abstract_actions:
                    return ACTION_BET_66
                return ACTION_CHECK_CALL
            elif equity > 0.45:
                # Medium hand, small bet or check
                if random.random() < 0.5 and ACTION_BET_33 in abstract_actions:
                    return ACTION_BET_33
                return ACTION_CHECK_CALL
            else:
                # Weak hand, check
                return ACTION_CHECK_CALL
    
    def _estimate_equity(self, my_cards, board_cards, discarded_by_us, 
                        discarded_by_opp, num_samples=50):
        """
        Estimate equity via Monte Carlo sampling.
        """
        if not my_cards:
            return 0.5
        
        # Build deck of remaining cards
        all_known = set(my_cards + board_cards)
        if discarded_by_us:
            all_known.add(discarded_by_us)
        if discarded_by_opp:
            all_known.add(discarded_by_opp)
        
        from hand_evaluator import RANKS, SUITS
        deck = [r + s for r in RANKS for s in SUITS if r + s not in all_known]
        
        wins = 0
        ties = 0
        
        for _ in range(num_samples):
            # Sample opponent cards and remaining board
            random.shuffle(deck)
            
            # Opponent has some cards (we don't know how many they kept)
            opp_cards = deck[:2]
            remaining_deck = deck[2:]
            
            # Complete the board if needed
            cards_needed = 6 - len(board_cards)  # Target is 6 board cards total
            sampled_board = board_cards + remaining_deck[:cards_needed]
            
            # Evaluate hands
            my_hand = my_cards + sampled_board
            opp_hand = opp_cards + sampled_board
            
            result = compare_hands(my_hand, opp_hand)
            
            if result > 0:
                wins += 1
            elif result == 0:
                ties += 1
        
        equity = (wins + 0.5 * ties) / num_samples
        return equity


if __name__ == "__main__":
    # Test the policy
    print("Testing CFR policy...")
    
    policy = CFRPolicy()
    
    # Test discard decision
    my_cards = ["As", "7h", "2d"]
    board = ["Kh", "Qd"]
    
    discard_idx = policy.get_discard_decision(my_cards, board, player_id=0, position=True)
    print(f"Discard decision for {my_cards} with board {board}: discard index {discard_idx}")
    
    # Test betting decision
    legal = {CheckAction, RaiseAction}
    action = policy.get_betting_decision(
        my_cards=["As", "Kh"],
        board_cards=["Qh", "Jh", "Th"],
        discarded_by_us="7h",
        discarded_by_opp=None,
        street=4,
        my_pip=0,
        opp_pip=0,
        my_stack=200,
        opp_stack=200,
        pot=20,
        legal_actions=legal,
        player_id=0,
        position=True,
        betting_history=[]
    )
    
    print(f"Betting decision: {action}")


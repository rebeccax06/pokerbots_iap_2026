'''
Simplified game abstraction for MCCFR training.
Represents the poker game state with action abstraction.
'''

import random
from copy import deepcopy
from hand_evaluator import evaluate_hand, compare_hands, RANKS, SUITS
from bucketing import get_infoset_key


# Action abstraction
ACTION_FOLD = 0
ACTION_CHECK_CALL = 1
ACTION_BET_33 = 2  # ~1/3 pot
ACTION_BET_66 = 3  # ~2/3 pot
ACTION_BET_POT = 4  # pot-sized
ACTION_ALL_IN = 5
ACTION_DISCARD_0 = 6  # Discard card at index 0
ACTION_DISCARD_1 = 7
ACTION_DISCARD_2 = 8

ACTION_NAMES = {
    ACTION_FOLD: "FOLD",
    ACTION_CHECK_CALL: "CHECK/CALL",
    ACTION_BET_33: "BET_33",
    ACTION_BET_66: "BET_66",
    ACTION_BET_POT: "BET_POT",
    ACTION_ALL_IN: "ALL_IN",
    ACTION_DISCARD_0: "DISCARD_0",
    ACTION_DISCARD_1: "DISCARD_1",
    ACTION_DISCARD_2: "DISCARD_2",
}

# Game constants
STARTING_STACK = 400
BIG_BLIND = 2
SMALL_BLIND = 1


class GameState:
    """
    Represents a simplified poker game state for MCCFR training.
    """
    
    def __init__(self):
        """Initialize a new hand."""
        # Initialize deck
        self.deck = [rank + suit for rank in RANKS for suit in SUITS]
        random.shuffle(self.deck)
        
        # Deal initial cards
        self.hole_cards = [
            [self.deck.pop() for _ in range(3)],  # Player 0
            [self.deck.pop() for _ in range(3)]   # Player 1
        ]
        
        # Board state
        self.board = []
        self.discarded_cards = [None, None]  # Cards discarded by each player
        
        # Betting state
        self.stacks = [STARTING_STACK - SMALL_BLIND, STARTING_STACK - BIG_BLIND]
        self.pips = [SMALL_BLIND, BIG_BLIND]  # Amount put in pot this street
        self.pot = SMALL_BLIND + BIG_BLIND
        
        # Game flow
        self.street = 0  # 0=preflop, 2=flop, 3=discard, 4=turn, 5=river
        self.active_player = 0  # Who acts next (0 or 1)
        self.button = 0  # Small blind position
        
        # History
        self.betting_history = [[]]  # List of action codes per street
        self.is_terminal = False
        self.winner = None
        self.payoffs = [0, 0]
        
        # Deal flop (2 cards for this variant)
        self.board = [self.deck.pop() for _ in range(2)]
    
    def copy(self):
        """Create a deep copy of this state."""
        return deepcopy(self)
    
    def get_legal_actions(self):
        """
        Return list of legal action codes for the active player.
        """
        if self.is_terminal:
            return []
        
        # Discard phase
        if self.street in [2, 3]:
            if len(self.hole_cards[self.active_player]) == 3:
                return [ACTION_DISCARD_0, ACTION_DISCARD_1, ACTION_DISCARD_2]
            else:
                # Already discarded, just pass turn
                return []
        
        # Betting phase
        facing_bet = self.pips[1 - self.active_player] > self.pips[self.active_player]
        amount_to_call = self.pips[1 - self.active_player] - self.pips[self.active_player]
        
        actions = []
        
        if facing_bet:
            # Can fold, call, or raise
            actions.append(ACTION_FOLD)
            if amount_to_call <= self.stacks[self.active_player]:
                actions.append(ACTION_CHECK_CALL)
            
            # Can raise if we have chips left after calling
            if self.stacks[self.active_player] > amount_to_call:
                remaining = self.stacks[self.active_player] - amount_to_call
                current_pot = self.pot + amount_to_call
                
                # Add raise options based on remaining stack
                if remaining >= current_pot * 0.33:
                    actions.append(ACTION_BET_33)
                if remaining >= current_pot * 0.66:
                    actions.append(ACTION_BET_66)
                if remaining >= current_pot:
                    actions.append(ACTION_BET_POT)
                if remaining < current_pot or remaining == self.stacks[self.active_player]:
                    actions.append(ACTION_ALL_IN)
        else:
            # Can check or bet
            actions.append(ACTION_CHECK_CALL)
            
            # Can bet if we have chips
            if self.stacks[self.active_player] > 0:
                current_pot = self.pot
                stack = self.stacks[self.active_player]
                
                if stack >= current_pot * 0.33:
                    actions.append(ACTION_BET_33)
                if stack >= current_pot * 0.66:
                    actions.append(ACTION_BET_66)
                if stack >= current_pot:
                    actions.append(ACTION_BET_POT)
                actions.append(ACTION_ALL_IN)
        
        return actions
    
    def apply_action(self, action):
        """
        Apply an action and transition to next state.
        Modifies state in-place.
        """
        if self.is_terminal:
            return
        
        player = self.active_player
        
        # Handle discard actions
        if action in [ACTION_DISCARD_0, ACTION_DISCARD_1, ACTION_DISCARD_2]:
            discard_idx = action - ACTION_DISCARD_0
            if discard_idx < len(self.hole_cards[player]):
                discarded = self.hole_cards[player].pop(discard_idx)
                self.discarded_cards[player] = discarded
                self.board.append(discarded)
            
            # Add to history
            self.betting_history[-1].append(str(action))
            
            # Check if both players have discarded
            if self.discarded_cards[0] is not None and self.discarded_cards[1] is not None:
                # Move to next street
                self._advance_street()
            else:
                # Switch to other player
                self.active_player = 1 - self.active_player
            
            return
        
        # Handle betting actions
        if action == ACTION_FOLD:
            # Opponent wins
            self.is_terminal = True
            self.winner = 1 - player
            chips_won = self.pot + self.pips[player]
            self.payoffs[self.winner] = chips_won - STARTING_STACK
            self.payoffs[player] = -(chips_won - STARTING_STACK)
            
        elif action == ACTION_CHECK_CALL:
            amount_to_call = self.pips[1 - player] - self.pips[player]
            
            # Put money in pot
            actual_call = min(amount_to_call, self.stacks[player])
            self.stacks[player] -= actual_call
            self.pips[player] += actual_call
            self.pot += actual_call
            
            # Check if both players have acted
            if self.pips[0] == self.pips[1]:
                self._advance_street()
            else:
                self.active_player = 1 - self.active_player
        
        else:
            # Betting actions
            current_pot = self.pot
            bet_size = 0
            
            if action == ACTION_BET_33:
                bet_size = int(current_pot * 0.33)
            elif action == ACTION_BET_66:
                bet_size = int(current_pot * 0.66)
            elif action == ACTION_BET_POT:
                bet_size = current_pot
            elif action == ACTION_ALL_IN:
                bet_size = self.stacks[player]
            
            # Ensure we don't bet more than our stack
            bet_size = min(bet_size, self.stacks[player])
            
            # Apply bet/raise
            amount_to_call = self.pips[1 - player] - self.pips[player]
            total_contribution = amount_to_call + bet_size
            
            self.stacks[player] -= total_contribution
            self.pips[player] += total_contribution
            self.pot += total_contribution
            
            # Opponent acts next
            self.active_player = 1 - self.active_player
        
        # Add to history
        self.betting_history[-1].append(str(action))
    
    def _advance_street(self):
        """Move to the next betting street."""
        # Reset pips for new betting round
        self.pips = [0, 0]
        
        if self.street == 0:
            # Preflop -> Flop (already dealt at init)
            self.street = 2
            self.active_player = 1  # Player 1 (big blind) acts first on flop
        elif self.street == 2:
            # Flop -> Discard phase
            self.street = 3
            self.active_player = 1  # Out of position player discards first
        elif self.street == 3:
            # Discard -> Turn
            if self.deck:
                self.board.append(self.deck.pop())
            self.street = 4
            self.active_player = 1
        elif self.street == 4:
            # Turn -> River
            if self.deck:
                self.board.append(self.deck.pop())
            self.street = 5
            self.active_player = 1
        elif self.street == 5:
            # River -> Showdown
            self._evaluate_showdown()
            return
        
        # Start new betting round
        self.betting_history.append([])
    
    def _evaluate_showdown(self):
        """Evaluate hands at showdown and determine winner."""
        self.is_terminal = True
        
        # Build each player's available cards (hole + board + own discard)
        cards0 = self.hole_cards[0] + self.board
        cards1 = self.hole_cards[1] + self.board
        
        result = compare_hands(cards0, cards1)
        
        if result > 0:
            self.winner = 0
        elif result < 0:
            self.winner = 1
        else:
            # Tie - split pot
            self.payoffs = [0, 0]
            return
        
        # Winner gets the pot
        loser = 1 - self.winner
        self.payoffs[self.winner] = (STARTING_STACK - self.stacks[self.winner]) - STARTING_STACK
        self.payoffs[loser] = (STARTING_STACK - self.stacks[loser]) - STARTING_STACK
    
    def get_infoset_key(self, player):
        """
        Get the information set key for the given player.
        This only includes information visible to that player.
        """
        position = (player == self.button)
        
        return get_infoset_key(
            player_id=player,
            hole_cards=self.hole_cards[player],
            board_cards=self.board,
            discarded_by_us=self.discarded_cards[player],
            discarded_by_opp=self.discarded_cards[1 - player],
            street=self.street,
            betting_history=self.betting_history[-1] if self.betting_history else [],
            position=position
        )
    
    def is_chance_node(self):
        """Returns True if this is a chance node (card dealing)."""
        # In our simplified model, we deal all cards at the start
        # So there are no chance nodes during play
        return False
    
    def __str__(self):
        """String representation for debugging."""
        s = f"Street {self.street}, Active: P{self.active_player}\n"
        s += f"Board: {self.board}\n"
        s += f"P0 cards: {self.hole_cards[0]}, Discarded: {self.discarded_cards[0]}\n"
        s += f"P1 cards: {self.hole_cards[1]}, Discarded: {self.discarded_cards[1]}\n"
        s += f"Pot: {self.pot}, Stacks: {self.stacks}, Pips: {self.pips}\n"
        if self.is_terminal:
            s += f"Terminal: Winner = P{self.winner}, Payoffs = {self.payoffs}\n"
        return s


if __name__ == "__main__":
    # Quick test
    print("Creating new game state...")
    state = GameState()
    print(state)
    
    print("\nLegal actions:", [ACTION_NAMES[a] for a in state.get_legal_actions()])
    
    print("\nTesting action application...")
    actions = state.get_legal_actions()
    if actions:
        state.apply_action(actions[0])
        print(state)



'''
MCCFR-based poker bot for Texas Hold'em Toss variant.
'''
from skeleton.actions import FoldAction, CallAction, CheckAction, RaiseAction, DiscardAction
from skeleton.states import GameState, TerminalState, RoundState
from skeleton.states import NUM_ROUNDS, STARTING_STACK, BIG_BLIND, SMALL_BLIND
from skeleton.bot import Bot
from skeleton.runner import parse_args, run_bot

import os
from cfr_policy import CFRPolicy


class Player(Bot):
    '''
    MCCFR-based poker bot.
    '''

    def __init__(self):
        '''
        Called when a new game starts. Called exactly once.

        Arguments:
        Nothing.

        Returns:
        Nothing.
        '''
        # Load trained strategy
        strategy_path = os.path.join(os.path.dirname(__file__), "cfr_strategy.pkl")
        self.policy = CFRPolicy(strategy_path)
        
        # Track game state
        self.my_discarded_card = None
        self.opp_discarded_card = None
        self.betting_history_current_street = []

    def handle_new_round(self, game_state, round_state, active):
        '''
        Called when a new round starts. Called NUM_ROUNDS times.

        Arguments:
        game_state: the GameState object.
        round_state: the RoundState object.
        active: your player's index.

        Returns:
        Nothing.
        '''
        # Reset round-specific tracking
        self.my_discarded_card = None
        self.opp_discarded_card = None
        self.betting_history_current_street = []

    def handle_round_over(self, game_state, terminal_state, active):
        '''
        Called when a round ends. Called NUM_ROUNDS times.

        Arguments:
        game_state: the GameState object.
        terminal_state: the TerminalState object.
        active: your player's index.

        Returns:
        Nothing.
        '''
        my_delta = terminal_state.deltas[active]  # your bankroll change from this round
        previous_state = terminal_state.previous_state  # RoundState before payoffs
        street = previous_state.street  # 0,2,3,4,5,6 representing when this round ended
        my_cards = previous_state.hands[active]  # your cards
        # opponent's cards or [] if not revealed
        opp_cards = previous_state.hands[1-active]
        pass

    def get_action(self, game_state, round_state, active):
        '''
        Where the magic happens - your code should implement this function.
        Called any time the engine needs an action from your bot.

        Arguments:
        game_state: the GameState object.
        round_state: the RoundState object.
        active: your player's index.

        Returns:
        Your action.
        '''
        legal_actions = round_state.legal_actions()  # the actions you are allowed to take
        # 0, 3, 4, or 5 representing pre-flop, flop, turn, or river respectively
        street = round_state.street
        my_cards = round_state.hands[active]  # your cards
        board_cards = round_state.board  # the board cards
        # the number of chips you have contributed to the pot this round of betting
        my_pip = round_state.pips[active]
        # the number of chips your opponent has contributed to the pot this round of betting
        opp_pip = round_state.pips[1-active]
        # the number of chips you have remaining
        my_stack = round_state.stacks[active]
        # the number of chips your opponent has remaining
        opp_stack = round_state.stacks[1-active]
        continue_cost = opp_pip - my_pip  # the number of chips needed to stay in the pot
        # the number of chips you have contributed to the pot
        my_contribution = STARTING_STACK - my_stack
        # the number of chips your opponent has contributed to the pot
        opp_contribution = STARTING_STACK - opp_stack
        pot = my_contribution + opp_contribution
        
        # Determine position
        position = (active == round_state.button)
        
        # Track discarded cards from board
        # Board starts with 2 flop cards, then discards are added
        if len(board_cards) > 2 and self.my_discarded_card is None:
            # Check if any board card is from discards
            # This is tricky - we need to track when cards appear on board
            # For now, we'll extract discards if possible
            if len(board_cards) == 3:
                # One player has discarded
                if len(my_cards) == 2:
                    # We've discarded, so board[-1] is ours
                    self.my_discarded_card = board_cards[-1]
                else:
                    # Opponent discarded
                    self.opp_discarded_card = board_cards[-1]
            elif len(board_cards) == 4:
                # Both have discarded
                if self.my_discarded_card is None and len(my_cards) == 2:
                    # Identify which cards are discards (last 2 added to board)
                    # This is approximate - in real engine we'd track better
                    pass
        
        # Reset betting history on new street
        if round_state.previous_state is None or round_state.previous_state.street != street:
            self.betting_history_current_street = []
        
        # Handle discard action
        if DiscardAction in legal_actions:
            discard_idx = self.policy.get_discard_decision(
                my_cards=my_cards,
                board_cards=board_cards,
                player_id=active,
                position=position
            )
            
            # Track our discard
            if discard_idx < len(my_cards):
                self.my_discarded_card = my_cards[discard_idx]
            
            action = DiscardAction(discard_idx)
            self.betting_history_current_street.append(f"D{discard_idx}")
            return action
        
        # Handle betting action
        action = self.policy.get_betting_decision(
            my_cards=my_cards,
            board_cards=board_cards,
            discarded_by_us=self.my_discarded_card,
            discarded_by_opp=self.opp_discarded_card,
            street=street,
            my_pip=my_pip,
            opp_pip=opp_pip,
            my_stack=my_stack,
            opp_stack=opp_stack,
            pot=pot,
            legal_actions=legal_actions,
            player_id=active,
            position=position,
            betting_history=self.betting_history_current_street
        )
        
        # Track action in history
        if isinstance(action, FoldAction):
            self.betting_history_current_street.append("F")
        elif isinstance(action, (CheckAction, CallAction)):
            self.betting_history_current_street.append("C")
        elif isinstance(action, RaiseAction):
            self.betting_history_current_street.append("R")
        
        return action


if __name__ == '__main__':
    run_bot(Player(), parse_args())

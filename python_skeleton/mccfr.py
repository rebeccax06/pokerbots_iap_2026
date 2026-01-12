'''
Monte Carlo Counterfactual Regret Minimization (MCCFR) implementation.
Uses external sampling for efficient training.
'''

import random
import pickle
from collections import defaultdict
from game_abstraction import GameState, ACTION_NAMES


class MCCFRTrainer:
    """
    MCCFR trainer using external sampling.
    """
    
    def __init__(self):
        """Initialize trainer with empty strategy tables."""
        # regret_sum[infoset][action] = cumulative regret
        self.regret_sum = defaultdict(lambda: defaultdict(float))
        
        # strategy_sum[infoset][action] = cumulative strategy (for averaging)
        self.strategy_sum = defaultdict(lambda: defaultdict(float))
        
        # Current iteration count
        self.iteration = 0
    
    def get_strategy(self, infoset, legal_actions):
        """
        Compute current strategy using regret matching.
        
        Args:
            infoset: Information set key (string)
            legal_actions: List of legal action codes
        
        Returns:
            Dict mapping action -> probability
        """
        if not legal_actions:
            return {}
        
        # Get regrets for this infoset
        regrets = self.regret_sum[infoset]
        
        # Compute positive regrets
        positive_regrets = {}
        total_positive = 0.0
        
        for action in legal_actions:
            regret = max(0.0, regrets[action])
            positive_regrets[action] = regret
            total_positive += regret
        
        # If no positive regrets, use uniform distribution
        if total_positive <= 0:
            prob = 1.0 / len(legal_actions)
            return {action: prob for action in legal_actions}
        
        # Normalize positive regrets to get strategy
        strategy = {}
        for action in legal_actions:
            strategy[action] = positive_regrets[action] / total_positive
        
        return strategy
    
    def get_average_strategy(self, infoset, legal_actions):
        """
        Get the average strategy for this infoset (used at runtime).
        
        Args:
            infoset: Information set key
            legal_actions: List of legal actions
        
        Returns:
            Dict mapping action -> probability
        """
        if not legal_actions:
            return {}
        
        strategy_totals = self.strategy_sum[infoset]
        
        total = sum(strategy_totals.get(action, 0.0) for action in legal_actions)
        
        if total <= 0:
            # No data, use uniform
            prob = 1.0 / len(legal_actions)
            return {action: prob for action in legal_actions}
        
        # Normalize
        avg_strategy = {}
        for action in legal_actions:
            avg_strategy[action] = strategy_totals[action] / total
        
        return avg_strategy
    
    def sample_action(self, strategy):
        """
        Sample an action according to the given strategy.
        
        Args:
            strategy: Dict mapping action -> probability
        
        Returns:
            Sampled action code
        """
        if not strategy:
            return None
        
        actions = list(strategy.keys())
        probs = [strategy[a] for a in actions]
        
        return random.choices(actions, weights=probs)[0]
    
    def train_iteration(self, traverser):
        """
        Run one iteration of external sampling MCCFR.
        
        Args:
            traverser: Player whose regrets we update (0 or 1)
        
        Returns:
            Expected value for the traverser
        """
        # Create a new game
        state = GameState()
        
        # Run CFR from the initial state
        return self._cfr_external(state, traverser, 1.0, 1.0)
    
    def _cfr_external(self, state, traverser, reach_prob_0, reach_prob_1):
        """
        External sampling CFR recursion.
        
        Args:
            state: Current game state
            traverser: Player whose regrets we're updating (0 or 1)
            reach_prob_0: Probability player 0 reaches this state
            reach_prob_1: Probability player 1 reaches this state
        
        Returns:
            Expected value for the traverser at this state
        """
        # Terminal node
        if state.is_terminal:
            return state.payoffs[traverser]
        
        player = state.active_player
        legal_actions = state.get_legal_actions()
        
        if not legal_actions:
            # No legal actions (shouldn't happen), advance
            state._advance_street()
            return self._cfr_external(state, traverser, reach_prob_0, reach_prob_1)
        
        infoset = state.get_infoset_key(player)
        
        # Get current strategy
        strategy = self.get_strategy(infoset, legal_actions)
        
        # If this is the traverser's node, compute counterfactual values
        if player == traverser:
            # Sample one action for opponent actions
            # But compute exact counterfactual values for traverser
            action_values = {}
            
            for action in legal_actions:
                # Make a copy and apply action
                next_state = state.copy()
                next_state.apply_action(action)
                
                # Recurse
                if player == 0:
                    action_values[action] = self._cfr_external(
                        next_state, traverser, 
                        reach_prob_0 * strategy[action], 
                        reach_prob_1
                    )
                else:
                    action_values[action] = self._cfr_external(
                        next_state, traverser,
                        reach_prob_0,
                        reach_prob_1 * strategy[action]
                    )
            
            # Expected value at this node
            node_value = sum(strategy[a] * action_values[a] for a in legal_actions)
            
            # Update regrets
            opponent_reach = reach_prob_1 if player == 0 else reach_prob_0
            
            for action in legal_actions:
                regret = action_values[action] - node_value
                self.regret_sum[infoset][action] += opponent_reach * regret
            
            # Update strategy sum (for average strategy)
            my_reach = reach_prob_0 if player == 0 else reach_prob_1
            for action in legal_actions:
                self.strategy_sum[infoset][action] += my_reach * strategy[action]
            
            return node_value
        
        else:
            # Opponent node: sample one action
            action = self.sample_action(strategy)
            
            next_state = state.copy()
            next_state.apply_action(action)
            
            if player == 0:
                return self._cfr_external(
                    next_state, traverser,
                    reach_prob_0 * strategy[action],
                    reach_prob_1
                )
            else:
                return self._cfr_external(
                    next_state, traverser,
                    reach_prob_0,
                    reach_prob_1 * strategy[action]
                )
    
    def train(self, iterations, verbose=True, save_every=None, save_path=None):
        """
        Run multiple training iterations.
        
        Args:
            iterations: Number of iterations to run
            verbose: Whether to print progress
            save_every: Save checkpoint every N iterations (None to disable)
            save_path: Path to save checkpoints
        
        Returns:
            Average game value over iterations
        """
        total_value = 0.0
        
        for i in range(iterations):
            self.iteration += 1
            
            # Alternate which player we traverse (external sampling)
            traverser = i % 2
            
            value = self.train_iteration(traverser)
            total_value += value
            
            if verbose and (i + 1) % 100 == 0:
                avg_value = total_value / (i + 1)
                print(f"Iteration {i + 1}/{iterations}, Avg value: {avg_value:.4f}")
            
            # Save checkpoint
            if save_every and save_path and (i + 1) % save_every == 0:
                self.save_strategy(save_path)
                if verbose:
                    print(f"Saved checkpoint to {save_path}")
        
        return total_value / iterations
    
    def save_strategy(self, filepath):
        """
        Save the average strategy to a file.
        
        Args:
            filepath: Path to save strategy
        """
        # Convert to regular dicts for pickling
        strategy_table = {}
        
        # Get all infosets
        all_infosets = set(self.strategy_sum.keys())
        
        for infoset in all_infosets:
            # We don't know legal actions here, so save raw strategy_sum
            strategy_table[infoset] = dict(self.strategy_sum[infoset])
        
        data = {
            'strategy_sum': strategy_table,
            'iteration': self.iteration
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
    
    def load_strategy(self, filepath):
        """
        Load a saved strategy.
        
        Args:
            filepath: Path to load strategy from
        """
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        
        self.strategy_sum = defaultdict(lambda: defaultdict(float))
        
        for infoset, actions in data['strategy_sum'].items():
            for action, value in actions.items():
                self.strategy_sum[infoset][action] = value
        
        self.iteration = data.get('iteration', 0)
    
    def get_exploitability(self, num_samples=100):
        """
        Estimate exploitability by computing best response value.
        This is a rough estimate using sampling.
        
        Args:
            num_samples: Number of games to sample
        
        Returns:
            Estimated exploitability (average best response value)
        """
        # This is a simplified exploitability estimate
        # A full best response computation would be more accurate but expensive
        total_value = 0.0
        
        for _ in range(num_samples):
            state = GameState()
            value = self._evaluate_strategy(state, player=0)
            total_value += value
        
        return abs(total_value / num_samples)
    
    def _evaluate_strategy(self, state, player):
        """
        Evaluate the average strategy by playing out a game.
        """
        if state.is_terminal:
            return state.payoffs[player]
        
        active = state.active_player
        legal_actions = state.get_legal_actions()
        
        if not legal_actions:
            state._advance_street()
            return self._evaluate_strategy(state, player)
        
        infoset = state.get_infoset_key(active)
        strategy = self.get_average_strategy(infoset, legal_actions)
        action = self.sample_action(strategy)
        
        state.apply_action(action)
        return self._evaluate_strategy(state, player)


if __name__ == "__main__":
    # Quick test
    print("Testing MCCFR trainer...")
    trainer = MCCFRTrainer()
    
    print("Running 100 training iterations...")
    avg_value = trainer.train(100, verbose=True)
    print(f"Average game value: {avg_value:.4f}")
    
    print(f"\nNumber of infosets learned: {len(trainer.strategy_sum)}")
    
    # Show a few example strategies
    print("\nExample strategies (first 5 infosets):")
    for i, infoset in enumerate(list(trainer.strategy_sum.keys())[:5]):
        actions = trainer.strategy_sum[infoset]
        print(f"{infoset}:")
        for action, count in actions.items():
            if action in ACTION_NAMES:
                print(f"  {ACTION_NAMES[action]}: {count:.2f}")



#!/usr/bin/env python3
'''
Example usage of the MCCFR bot components.
Demonstrates how the different modules work together.
'''

import os
import sys


def example_hand_evaluation():
    """Example: Evaluating poker hands"""
    print("=" * 60)
    print("Example 1: Hand Evaluation")
    print("=" * 60)
    
    from hand_evaluator import evaluate_hand, compare_hands, get_hand_strength_category
    
    # Example hands
    hand1 = ["As", "Ah", "Kh", "Qh", "Jh", "Th", "9h"]  # Strong flush
    hand2 = ["2d", "2c", "7s", "8h", "9c", "Jd", "Kc"]  # Pair of 2s
    
    score1 = evaluate_hand(tuple(hand1))
    score2 = evaluate_hand(tuple(hand2))
    
    print(f"Hand 1: {hand1}")
    print(f"  Score: {score1}")
    print(f"  Category: {get_hand_strength_category(hand1)}")
    
    print(f"\nHand 2: {hand2}")
    print(f"  Score: {score2}")
    print(f"  Category: {get_hand_strength_category(hand2)}")
    
    result = compare_hands(hand1, hand2)
    winner = "Hand 1" if result > 0 else ("Hand 2" if result < 0 else "Tie")
    print(f"\nWinner: {winner}")


def example_bucketing():
    """Example: State abstraction via bucketing"""
    print("\n" + "=" * 60)
    print("Example 2: Bucketing")
    print("=" * 60)
    
    from bucketing import get_preflop_bucket, get_postflop_bucket, get_infoset_key
    
    # Preflop example
    hole_cards = ["As", "Ah", "Kd"]
    print(f"Hole cards: {hole_cards}")
    bucket = get_preflop_bucket(hole_cards)
    print(f"Preflop bucket: {bucket}")
    
    # Postflop example
    board = ["Kh", "Qh", "Jh"]
    print(f"\nBoard: {board}")
    bucket = get_postflop_bucket(["As", "Ah"], board)
    print(f"Postflop bucket: {bucket}")
    
    # Full infoset key
    infoset = get_infoset_key(
        player_id=0,
        hole_cards=["As", "Ah"],
        board_cards=board,
        discarded_by_us="Kd",
        discarded_by_opp=None,
        street=4,
        betting_history=["1", "2"],
        position=True
    )
    print(f"\nFull infoset key: {infoset}")


def example_game_simulation():
    """Example: Simulating a poker hand"""
    print("\n" + "=" * 60)
    print("Example 3: Game Simulation")
    print("=" * 60)
    
    from game_abstraction import GameState, ACTION_CHECK_CALL, ACTION_DISCARD_0
    
    # Create a new game
    state = GameState()
    
    print("Initial state:")
    print(f"  Player 0 cards: {state.hole_cards[0]}")
    print(f"  Player 1 cards: {state.hole_cards[1]}")
    print(f"  Board: {state.board}")
    print(f"  Pot: {state.pot}")
    print(f"  Active player: {state.active_player}")
    
    # Player 0 action
    legal = state.get_legal_actions()
    print(f"\nLegal actions: {legal[:3]}...")
    
    if ACTION_CHECK_CALL in legal:
        state.apply_action(ACTION_CHECK_CALL)
        print("Player 0: CHECK/CALL")
    
    print(f"Active player after action: {state.active_player}")
    print(f"Street: {state.street}")


def example_training():
    """Example: Quick training run"""
    print("\n" + "=" * 60)
    print("Example 4: Training (Quick Demo)")
    print("=" * 60)
    
    from mccfr import MCCFRTrainer
    
    print("Training for 50 iterations (demo)...")
    trainer = MCCFRTrainer()
    
    avg_value = trainer.train(iterations=50, verbose=False)
    
    print(f"Average game value: {avg_value:.6f}")
    print(f"Information sets learned: {len(trainer.strategy_sum)}")
    
    # Show a sample infoset
    if trainer.strategy_sum:
        infoset = list(trainer.strategy_sum.keys())[0]
        print(f"\nSample infoset: {infoset}")
        
        from game_abstraction import ACTION_NAMES
        actions = trainer.strategy_sum[infoset]
        total = sum(actions.values())
        
        print("Strategy:")
        for action, count in list(actions.items())[:3]:
            prob = count / total if total > 0 else 0
            action_name = ACTION_NAMES.get(int(action), f"Action {action}")
            print(f"  {action_name}: {prob:.3f}")


def example_policy_usage():
    """Example: Using the policy at runtime"""
    print("\n" + "=" * 60)
    print("Example 5: Policy Usage (Runtime)")
    print("=" * 60)
    
    from cfr_policy import CFRPolicy
    from skeleton.actions import CheckAction, RaiseAction
    
    # Create policy (no strategy file, uses fallback)
    policy = CFRPolicy()
    
    print("Policy created (using fallback heuristic)")
    
    # Example discard decision
    my_cards = ["As", "7h", "2d"]
    board = ["Kh", "Qd"]
    
    discard_idx = policy.get_discard_decision(
        my_cards=my_cards,
        board_cards=board,
        player_id=0,
        position=True
    )
    
    print(f"\nDiscard decision for {my_cards}:")
    print(f"  Discard index: {discard_idx} (card: {my_cards[discard_idx]})")
    
    # Example betting decision
    legal_actions = {CheckAction, RaiseAction}
    
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
        legal_actions=legal_actions,
        player_id=0,
        position=True,
        betting_history=[]
    )
    
    print(f"\nBetting decision with strong hand:")
    print(f"  Action: {action}")


def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print("MCCFR Bot - Example Usage")
    print("=" * 60)
    print("This script demonstrates the key components of the bot.")
    print()
    
    try:
        example_hand_evaluation()
        example_bucketing()
        example_game_simulation()
        example_training()
        example_policy_usage()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        print("\nTo train a full bot:")
        print("  python train_cfr.py --iterations 50000 --output cfr_strategy.pkl")
        print("\nTo use the bot:")
        print("  python player.py")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()



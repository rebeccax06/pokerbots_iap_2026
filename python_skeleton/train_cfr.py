#!/usr/bin/env python3
'''
Training script for MCCFR poker bot.

Usage:
    python train_cfr.py --iterations 10000 --output cfr_strategy.pkl
    python train_cfr.py --iterations 50000 --output cfr_strategy.pkl --verbose
    python train_cfr.py --iterations 100000 --output cfr_strategy.pkl --save-every 5000
'''

import argparse
import time
from mccfr import MCCFRTrainer
from game_abstraction import ACTION_NAMES

def main():
    parser = argparse.ArgumentParser(description='Train MCCFR poker bot')
    
    parser.add_argument(
        '--iterations',
        type=int,
        default=10000,
        help='Number of training iterations (default: 10000)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        default='cfr_strategy.pkl',
        help='Output file path for trained strategy (default: cfr_strategy.pkl)'
    )
    
    parser.add_argument(
        '--load',
        type=str,
        default=None,
        help='Load existing strategy to continue training (default: None)'
    )
    
    parser.add_argument(
        '--save-every',
        type=int,
        default=None,
        help='Save checkpoint every N iterations (default: only save at end)'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Print progress information'
    )
    
    parser.add_argument(
        '--eval-every',
        type=int,
        default=None,
        help='Evaluate exploitability every N iterations (default: None, expensive)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("MCCFR Poker Bot Training")
    print("=" * 60)
    print(f"Iterations: {args.iterations}")
    print(f"Output file: {args.output}")
    if args.load:
        print(f"Loading from: {args.load}")
    if args.save_every:
        print(f"Save checkpoint every: {args.save_every} iterations")
    print("=" * 60)
    
    # Initialize trainer
    trainer = MCCFRTrainer()
    
    # Load existing strategy if specified
    if args.load:
        try:
            print(f"Loading strategy from {args.load}...")
            trainer.load_strategy(args.load)
            print(f"Loaded strategy at iteration {trainer.iteration}")
        except Exception as e:
            print(f"Warning: Could not load strategy: {e}")
            print("Starting fresh training...")
    
    # Training
    print("\nStarting training...\n")
    start_time = time.time()
    
    try:
        avg_value = trainer.train(
            iterations=args.iterations,
            verbose=args.verbose or True,
            save_every=args.save_every,
            save_path=args.output if args.save_every else None
        )
        
        elapsed = time.time() - start_time
        
        print("\n" + "=" * 60)
        print("Training Complete!")
        print("=" * 60)
        print(f"Total iterations: {trainer.iteration}")
        print(f"Average game value: {avg_value:.6f}")
        print(f"Time elapsed: {elapsed:.2f} seconds")
        print(f"Iterations per second: {args.iterations / elapsed:.2f}")
        print(f"Information sets learned: {len(trainer.strategy_sum)}")
        
        # Evaluate exploitability if requested
        if args.eval_every or args.iterations <= 1000:
            print("\nEstimating exploitability (this may take a moment)...")
            exploitability = trainer.get_exploitability(num_samples=100)
            print(f"Estimated exploitability: {exploitability:.6f}")
        
        # Save final strategy
        print(f"\nSaving strategy to {args.output}...")
        trainer.save_strategy(args.output)
        print("Strategy saved successfully!")
        
        # Print some sample strategies
        print("\n" + "=" * 60)
        print("Sample Information Sets (first 10):")
        print("=" * 60)
        
        
        
        for i, infoset in enumerate(list(trainer.strategy_sum.keys())[:10]):
            print(f"\n{i+1}. {infoset}")
            
            # Get all actions for this infoset
            actions = trainer.strategy_sum[infoset]
            total = sum(actions.values())
            
            if total > 0:
                print("   Strategy:")
                for action, count in sorted(actions.items(), key=lambda x: x[1], reverse=True):
                    prob = count / total
                    action_name = ACTION_NAMES.get(int(action), f"Action {action}")
                    print(f"     {action_name}: {prob:.3f}")
        
        print("\n" + "=" * 60)
        print("Training complete! Use this strategy file with player.py")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\nTraining interrupted by user!")
        print("Saving current progress...")
        trainer.save_strategy(args.output)
        print(f"Strategy saved to {args.output}")
        print(f"Completed {trainer.iteration} iterations")
    
    except Exception as e:
        print(f"\n\nError during training: {e}")
        import traceback
        traceback.print_exc()
        print("\nAttempting to save progress...")
        try:
            trainer.save_strategy(args.output + ".error_backup")
            print(f"Progress saved to {args.output}.error_backup")
        except:
            print("Could not save progress")


if __name__ == "__main__":
    main()



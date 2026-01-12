# MCCFR Poker Bot for Texas Hold'em Toss Variant

This is an implementation of a Monte Carlo Counterfactual Regret Minimization (MCCFR) bot for a special variant of Texas Hold'em poker with a "discard/toss" phase.

## Game Rules

- Each player starts with 3 hole cards
- Flop is 2 board cards (instead of 3)
- Discard phase: each player discards 1 card onto the board (becomes public)
- After both discards, there are 4 board cards
- Turn and river follow normally
- Stacks reset each hand
- Hand evaluation: best 5-card hand from all available cards (original 3 hole cards + board)

## Architecture

### Core Modules

1. **hand_evaluator.py** - Fast 7-card poker hand evaluation
   - Evaluates best 5-card hand from up to 7 cards
   - Returns hand category (high card, pair, two pair, etc.)
   - Includes hand comparison and strength estimation

2. **bucketing.py** - Information set abstraction
   - Maps game states to coarse buckets to reduce memory
   - Preflop bucketing based on card ranks and suitedness
   - Postflop bucketing based on hand strength and board texture
   - Special discard phase bucketing

3. **game_abstraction.py** - Simplified game model for training
   - Represents poker game state with action abstraction
   - Action abstraction: FOLD, CHECK/CALL, BET_33, BET_66, BET_POT, ALL_IN, DISCARD
   - Handles betting, discarding, and showdowns
   - Generates information set keys

4. **mccfr.py** - MCCFR training algorithm
   - External sampling MCCFR implementation
   - Regret matching for strategy computation
   - Average strategy for final policy
   - Save/load trained strategies

5. **cfr_policy.py** - Runtime policy
   - Loads trained strategy
   - Maps game states to abstract actions
   - Converts abstract actions to engine actions
   - Fallback heuristic if no strategy loaded

6. **player.py** - Main bot interface
   - Integrates with game engine
   - Uses trained policy for decisions
   - Tracks game state (discards, betting history)

7. **train_cfr.py** - Training script
   - Command-line interface for training
   - Progress tracking and checkpointing
   - Exploitability estimation

## Installation

No external dependencies beyond Python standard library! All code is self-contained.

```bash
cd python_skeleton
```

## Usage

### 1. Train the Bot

Train a strategy using MCCFR:

```bash
# Quick training (10K iterations, ~1-2 minutes)
python train_cfr.py --iterations 10000 --output cfr_strategy.pkl --verbose

# Standard training (50K iterations, ~5-10 minutes)
python train_cfr.py --iterations 50000 --output cfr_strategy.pkl --verbose

# Extended training (100K+ iterations, better performance)
python train_cfr.py --iterations 100000 --output cfr_strategy.pkl --save-every 10000 --verbose
```

Training options:
- `--iterations N`: Number of training iterations (default: 10000)
- `--output FILE`: Output file for trained strategy (default: cfr_strategy.pkl)
- `--load FILE`: Continue training from existing strategy
- `--save-every N`: Save checkpoint every N iterations
- `--verbose`: Print progress information
- `--eval-every N`: Evaluate exploitability every N iterations (expensive)

### 2. Run the Bot

Once trained, the bot will automatically load `cfr_strategy.pkl` when playing:

```bash
python player.py
```

The bot expects the strategy file to be in the same directory as `player.py`.

### 3. Testing Individual Components

You can test individual modules:

```bash
# Test hand evaluator
python hand_evaluator.py

# Test bucketing
python bucketing.py

# Test game abstraction
python game_abstraction.py

# Test MCCFR (runs mini training)
python mccfr.py

# Test policy
python cfr_policy.py
```

## Implementation Details

### Action Abstraction

The bot uses a simplified action space to make training tractable:

**Betting actions:**
- FOLD (when facing a bet)
- CHECK/CALL
- BET_33 (~1/3 pot)
- BET_66 (~2/3 pot)
- BET_POT (pot-sized bet)
- ALL_IN

**Discard actions:**
- DISCARD_0 (discard card at index 0)
- DISCARD_1 (discard card at index 1)
- DISCARD_2 (discard card at index 2)

### Information Set Abstraction

To keep memory manageable, game states are mapped to coarse "buckets":

**Preflop:**
- Trips vs. high pair vs. mid pair vs. low pair
- High cards vs. mid cards vs. low cards
- Suited vs. offsuit

**Postflop:**
- Hand strength category (0-8: high card through straight flush)
- Board texture (paired, trips, flush draw, connected)

**Information set key format:**
`s{street}_{position}_{bucket}_{betting_history}`

Example: `s4_btn_cat5_rainbow_flush_CR`
- Street 4 (turn)
- Button position
- Category 5 hand (flush)
- Rainbow board with flush draw
- Betting history: Check, Raise

### MCCFR Algorithm

- **External sampling**: Sample one action for opponent, compute exact counterfactual values for traverser
- **Alternating traverser**: Alternate which player we update each iteration
- **Regret matching**: Strategy = normalized positive regrets
- **Average strategy**: Final policy is average over all iterations

### Fallback Heuristic

If no trained strategy is available, the bot uses a simple heuristic:
- Monte Carlo equity estimation (50 samples)
- Pot odds calculation
- Simple bet sizing based on hand strength

## Performance Characteristics

### Training Time

- 10K iterations: 1-2 minutes, basic strategy
- 50K iterations: 5-10 minutes, decent strategy
- 100K iterations: 10-20 minutes, good strategy
- 500K+ iterations: 1+ hour, strong strategy

### Runtime Performance

- Strategy lookup: O(1) hash table lookup
- Action decision: < 0.001s per action (well within time limits)
- Memory usage: ~10-50MB depending on training iterations

### Strategy Quality

With 50K+ iterations:
- Reasonable preflop strategy (fold bad hands, raise good hands)
- Sensible discard decisions (generally keeps best 2 cards)
- Appropriate bet sizing based on hand strength
- Basic bluffing and value betting

With 500K+ iterations:
- Strong overall strategy approaching Nash equilibrium
- Balanced ranges (hard to exploit)
- Mixed strategies (bluffs and traps)

## Customization

### Adjusting Action Abstraction

Edit `game_abstraction.py`:
- Modify bet sizing percentages (e.g., add BET_50 for half-pot)
- Add/remove actions in `ACTION_*` constants
- Update `get_legal_actions()` to include new actions

### Adjusting Bucketing

Edit `bucketing.py`:
- Modify `get_preflop_bucket()` for finer/coarser preflop buckets
- Modify `get_postflop_bucket()` for different postflop abstractions
- Consider adding potential-aware bucketing (draw strength)

### Adjusting Training

Edit `mccfr.py`:
- Switch from external sampling to outcome sampling
- Add pruning (prune low-probability branches)
- Add linear CFR or CFR+ for faster convergence
- Implement Monte Carlo sampling for opponent cards at showdown

## Debugging

### Check Strategy File

```python
import pickle

with open('cfr_strategy.pkl', 'rb') as f:
    data = pickle.load(f)
    
print(f"Iterations trained: {data['iteration']}")
print(f"Number of infosets: {len(data['strategy_sum'])}")

# Look at a specific infoset
for infoset in list(data['strategy_sum'].keys())[:5]:
    print(f"\n{infoset}:")
    print(data['strategy_sum'][infoset])
```

### Monitor Training

Watch for:
- Average game value should oscillate around 0 (zero-sum game)
- Number of infosets should grow initially then plateau
- Exploitability should decrease over time

### Test Hand Evaluation

```python
from hand_evaluator import evaluate_hand, compare_hands

cards = ["As", "Ah", "Kh", "Qh", "Jh", "Th", "9h"]
score = evaluate_hand(tuple(cards))
print(f"Hand score: {score}")  # Should be very high (royal flush)
```

## Known Limitations

1. **No card removal effects**: Training doesn't account for blocker effects
2. **Coarse bucketing**: Some +EV spots may be missed due to bucketing
3. **Fixed action abstraction**: Real bet sizes may differ slightly
4. **No opponent modeling**: Assumes opponent plays equilibrium strategy
5. **No game tree pruning**: Explores all branches (could be optimized)

## Future Improvements

1. **Better bucketing**: Use k-means clustering on hand equity distributions
2. **Imperfect recall abstraction**: Group similar betting sequences
3. **Strategy refinement**: Train against self for exploitative play
4. **Parallel training**: Multi-threaded iteration batches
5. **Incremental training**: Continue training during tournament

## References

- Zinkevich et al. (2007): "Regret Minimization in Games with Incomplete Information"
- Johanson et al. (2012): "Finding Optimal Abstract Strategies in Extensive-Form Games"
- Brown & Sandholm (2017): "Superhuman AI for heads-up no-limit poker: Libratus"
- Brown et al. (2019): "Superhuman AI for multiplayer poker"

## License

Educational/research use. Not for commercial poker playing.

## Author

Implemented for MIT Pokerbots 2026.



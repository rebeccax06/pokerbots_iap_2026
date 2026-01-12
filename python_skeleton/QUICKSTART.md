# Quick Start Guide

## Get Started in 3 Steps

### Step 1: Train Your Bot (5-10 minutes)

```bash
cd python_skeleton
python train_cfr.py --iterations 50000 --output cfr_strategy.pkl --verbose
```

This will:
- Train a poker bot using Monte Carlo CFR
- Save the strategy to `cfr_strategy.pkl`
- Show progress every 100 iterations
- Take approximately 5-10 minutes

### Step 2: Verify the Strategy

Check that the strategy file was created:

```bash
ls -lh cfr_strategy.pkl
```

You should see a file that's a few MB in size.

### Step 3: Run Your Bot

The bot will automatically load the strategy when playing:

```bash
python player.py
```

## What Just Happened?

1. **Training Phase** - The bot played thousands of hands against itself, learning optimal strategies for different situations

2. **Strategy Saved** - All learned strategies are stored in `cfr_strategy.pkl`

3. **Runtime** - When playing, the bot looks up the current situation and uses the learned strategy

## Training Tips

### Quick Training (Testing)
```bash
python train_cfr.py --iterations 10000 --output cfr_strategy.pkl
```
- Takes ~1-2 minutes
- Good for testing, not competitive

### Standard Training (Recommended)
```bash
python train_cfr.py --iterations 50000 --output cfr_strategy.pkl --verbose
```
- Takes ~5-10 minutes
- Decent performance

### Extended Training (Best Performance)
```bash
python train_cfr.py --iterations 200000 --output cfr_strategy.pkl --save-every 20000 --verbose
```
- Takes ~30-40 minutes
- Strong performance
- Saves checkpoints every 20K iterations

### Continue Training
```bash
python train_cfr.py --load cfr_strategy.pkl --iterations 50000 --output cfr_strategy.pkl --verbose
```
- Continues from existing strategy
- Useful for incremental improvement

## Understanding the Output

During training, you'll see:
```
Iteration 100/50000, Avg value: -0.0234
Iteration 200/50000, Avg value: 0.0123
...
```

- **Avg value**: Should oscillate around 0 (zero-sum game)
- **Iterations**: More iterations = better strategy (diminishing returns)

At the end:
```
Training Complete!
Total iterations: 50000
Average game value: 0.0012
Time elapsed: 387.45 seconds
Iterations per second: 129.08
Information sets learned: 8234
```

- **Information sets**: Number of unique situations learned (~5K-15K typical)
- **Iterations per second**: Performance metric (~100-200 typical)

## Troubleshooting

### "No module named 'skeleton'"
Make sure you're in the `python_skeleton` directory:
```bash
cd python_skeleton
python train_cfr.py ...
```

### Training is slow
- Normal for 100K+ iterations
- Consider starting with 10K for testing
- Training time scales linearly with iterations

### Bot plays randomly
- Check if `cfr_strategy.pkl` exists in the same directory as `player.py`
- Make sure training completed successfully
- Try retraining with more iterations

### Memory issues
- Reduce iterations (100K should be fine on most systems)
- Close other applications
- Typical memory usage: 10-50MB for strategy

## What's Next?

### Analyze Your Bot
```python
import pickle

with open('cfr_strategy.pkl', 'rb') as f:
    data = pickle.load(f)

print(f"Trained for {data['iteration']} iterations")
print(f"Learned {len(data['strategy_sum'])} situations")
```

### Improve Performance
1. Train for more iterations (200K, 500K, 1M)
2. Adjust bucketing in `bucketing.py`
3. Tune action abstraction in `game_abstraction.py`
4. Modify MCCFR parameters in `mccfr.py`

### Test Components
```bash
# Test hand evaluation
python hand_evaluator.py

# Test bucketing
python bucketing.py

# Test game simulation
python game_abstraction.py
```

## Key Files

- `player.py` - Your bot (submits this)
- `cfr_strategy.pkl` - Trained strategy (include with submission)
- `train_cfr.py` - Training script (use before tournament)
- `cfr_policy.py` - Runtime policy loader
- `hand_evaluator.py` - Hand evaluation
- `bucketing.py` - State abstraction
- `game_abstraction.py` - Game simulation
- `mccfr.py` - Training algorithm

## Performance Expectations

After 50K iterations:
- Plays reasonable preflop strategy
- Makes sensible discards
- Uses appropriate bet sizing
- Basic value betting and bluffing

After 200K+ iterations:
- Strong overall strategy
- Balanced play (hard to exploit)
- Good adaptation to board texture
- Mixed strategies in key spots

## Competition Tips

1. **Train overnight** - 500K-1M iterations for best results
2. **Test locally** - Run against the skeleton player
3. **Monitor memory** - Keep strategy file < 100MB
4. **Have backups** - Save multiple training checkpoints
5. **Keep fallback** - Heuristic kicks in if strategy missing

Good luck! 🎰



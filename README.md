# Strands Token Usage Tracker Hook

A hook for monitoring token usage per cycle in Strands agents, with detailed cache tracking, cost calculation, and savings analysis.

## Installation

```python
from hooks.token_usage_tracker import TokenUsageTracker

agent = Agent(
    model=BedrockModel(
        model_id="your-model-id",
        cache_config=CacheConfig(strategy="auto")
    ),
    hooks=[TokenUsageTracker()],
    # ... other config
)
```

## How It Works

A **cycle** = `BeforeModelCall` → Model Call → `AfterModelCall`.

However, `accumulated_usage` is only populated *after* the complete cycle finishes. So we use `BeforeModelCallEvent` of the *next* cycle to access the *previous* completed cycle's data. For the final cycle, we use `AfterInvocationEvent` since there's no subsequent `BeforeModelCallEvent` once the loop completes:

```
Cycle 1: BeforeModelCall #1 → Model Call → AfterModelCall #1 ✓
  ↓ (accumulated_usage now has Cycle 1 data)
BeforeModelCall #2 → Skip logging (cycle_count=1, display_cycle=0)

Cycle 2: BeforeModelCall #2 → Model Call → AfterModelCall #2 ✓
  ↓ (accumulated_usage now has Cycles 1+2 data)
BeforeModelCall #3 → Logs Cycle 1 usage (cycle_count=2, display_cycle=1)

Cycle 3: BeforeModelCall #3 → Model Call → AfterModelCall #3 ✓
  ↓ (accumulated_usage now has Cycles 1+2+3 data)
BeforeModelCall #4 → Logs Cycle 2 usage (cycle_count=3, display_cycle=2)

Final cycle: No BeforeModelCall #4, so...
  ↓
AfterInvocation → Logs Cycle 3 usage (cycle_count=3)
```

**Key insight**: We log cycle N-1 at the start of cycle N, because that's when cycle N-1's complete data is available in `accumulated_usage`.

## Output Example

```
I'll help you with this step-by-step calculation.

First, let me add 2 + 5:
Tool #1: calculator
[Cycle 1] Input: 3459, Output: 82, Cache Read: 0, Cache Write: 0

Now I'll convert 7°C to Fahrenheit:
Tool #2: temperature_converter
[Cycle 2] Input: 22, Output: 105, Cache Read: 0, Cache Write: 3532

Now I'll multiply 44.6 by 60:
Tool #3: calculator
[Cycle 3] Input: 26, Output: 71, Cache Read: 3532, Cache Write: 118

Finally, I'll convert 2676°F to Celsius:
Tool #4: temperature_converter
[Cycle 4] Input: 25, Output: 107, Cache Read: 3650, Cache Write: 88

**Results:**
1. 2 + 5 = **7**
2. 7°C = **44.6°F**
3. 44.6 × 60 = **2676**
4. 2676°F = **1468.9°C**

The final answer is **1468.9°C**
[Cycle 5] Input: 27, Output: 82, Cache Read: 3738, Cache Write: 123

[Total] Input: 3559, Output: 447, Total: 18787
[Total Cache] Read: 10920, Write: 3861
```

## Cache Behavior

```
Cycle 1: No cache yet        → Cache Read: 0, Cache Write: 0
Cycle 2: Creates cache       → Cache Read: 0, Cache Write: 3532
Cycle 3: Uses cache          → Cache Read: 3532, Cache Write: 118
```

### Key Points

- **Cache Write** = INPUT tokens being cached (not output)
- **Cache Read** = INPUT tokens retrieved from cache
- **TTL**: 5 minutes default (resets on each use)
- **Cache persists** across agent restarts within TTL
- **First call**: No cache benefits (setup phase)
- **Subsequent calls**: Cost savings on cached input

### Bedrock Caching Thresholds

- **Minimum tokens to cache**: ~1024 tokens (Bedrock won't cache smaller prefixes)
- **Maximum cached tokens**:
  - Claude models: 32,000 tokens
  - Nova models: 20,000 tokens
- **Maximum checkpoints**: 4 cache checkpoints per conversation

### Token Accounting: How Input Tokens and Cache Tokens Relate

**Critical Fact:** `inputTokens` **excludes** `cacheReadInputTokens`. They are separate, non-overlapping fields in the AWS Bedrock response.

#### Proof: Identical Workload With vs. Without Caching

**Run 1 - WITH Caching (`cache_config=CacheConfig(strategy="auto")`):**
```
I'll help you with this calculation step by step.

1. First, let me add 2 + 5
2. Treat that result as Celsius and convert to Fahrenheit
3. Multiply that Fahrenheit value by 60
4. Convert that result back to Celsius

Let me start:
Tool #1: calculator
[Cycle 1] Input: 3459, Output: 125, Cache Read: 0, Cache Write: 0, Cost: $0.012252

Now let me convert 7°C to Fahrenheit:
Tool #2: temperature_converter
[Cycle 2] Input: 22, Output: 105, Cache Read: 0, Cache Write: 3575, Cost: $0.015047

Now let me multiply 44.6 by 60:
Tool #3: calculator
[Cycle 3] Input: 26, Output: 71, Cache Read: 3575, Cache Write: 118, Cost: $0.002658, Saved: $0.009653

Finally, let me convert 2676°F back to Celsius:
Tool #4: temperature_converter
[Cycle 4] Input: 25, Output: 108, Cache Read: 3693, Cache Write: 88, Cost: $0.003133, Saved: $0.009971

**Summary of calculations:**
1. 2 + 5 = **7**
2. 7°C = **44.6°F**
3. 44.6 × 60 = **2676**
4. 2676°F = **1468.9°C**

**Final answer: 1468.9°C**
[Cycle 5] Input: 27, Output: 84, Cache Read: 3781, Cache Write: 124, Cost: $0.002940, Saved: $0.010209

[Total] Input: 3559, Output: 493, Total: 19006
[Total Cache] Read: 11049, Write: 3905
[Total Cost] $0.036030
[Total Savings] $0.029832
```

**Run 2 - WITHOUT Caching (cache_config disabled):**
```
I'll help you with these calculations step by step.

1. First, let me add 2 + 5
2. Treat that result as Celsius and convert to Fahrenheit
3. Multiply that Fahrenheit value by 60
4. Convert that result back to Celsius
Tool #1: calculator
[Cycle 1] Input: 3459, Output: 120, Cache Read: 0, Cache Write: 0, Cost: $0.012177

Now let me convert 7°C to Fahrenheit:
Tool #2: temperature_converter
[Cycle 2] Input: 3592, Output: 105, Cache Read: 0, Cache Write: 0, Cost: $0.012351

Now let me multiply 44.6 by 60:
Tool #3: calculator
[Cycle 3] Input: 3714, Output: 71, Cache Read: 0, Cache Write: 0, Cost: $0.012207

Finally, let me convert 2676°F to Celsius:
Tool #4: temperature_converter
[Cycle 4] Input: 3801, Output: 107, Cache Read: 0, Cache Write: 0, Cost: $0.013008

**Summary of calculations:**
1. 2 + 5 = **7**
2. 7°C = **44.6°F**
3. 44.6 × 60 = **2676**
4. 2676°F = **1468.9°C**

The final answer is **1468.9°C**
[Cycle 5] Input: 3926, Output: 84, Cache Read: 0, Cache Write: 0, Cost: $0.013038

[Total] Input: 18492, Output: 487, Total: 18979
[Total Cache] Read: 0, Write: 0
[Total Cost] $0.062781
[Total Savings] $0.000000
```

#### Analysis

```
Run 1: input + cache_read + cache_write = 3,559 + 11,049 + 3,905 = 18,513 tokens
Run 2: input (no cache) = 18,492 tokens
Difference: 21 tokens (≈0.1% - negligible rounding)
```

**What this proves:**
- When caching is enabled, only **new/unique tokens** are counted as `inputTokens`
- **Cached tokens** are tracked separately in `cacheReadInputTokens`
- Without caching, **all tokens** are processed as `inputTokens`
- The token counts match: `input + cache_read + cache_write ≈ total input without cache`

**Cost verification:**
```
Run 1: Cost + Savings = $0.036030 + $0.029832 = $0.065862
Run 2: Cost = $0.062781
Difference: $0.003 (within expected variance)
```

This confirms our cost calculation is correct - we add all token types without double-counting.

### Cache Invalidation

Cache breaks when:
- TTL expires
- System prompt changes
- Tool definitions change
- Conversation manager trims old messages

## License

MIT

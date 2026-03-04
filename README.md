# Strands Token Usage Tracker Hook

A hook for monitoring token usage per cycle in Strands agents, with detailed cache tracking, cost calculation, and savings analysis.

**Supported Models:**
- ✅ **All Bedrock models** - Input/output token tracking ([AWS: TokenUsage](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_TokenUsage.html))
- ✅ **Claude & Nova only** - Cache tracking (read/write) and savings analysis ([AWS: Supported models](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html#prompt-caching-models))

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
I'll help you with this calculation. Let me break it down:
1. Add 2 + 5
2. Treat the result as Celsius and convert to Fahrenheit
3. Multiply that Fahrenheit value by 60
4. Convert the result back to Celsius

Let me start:
Tool #1: calculator
[Cycle 1]
  Input: (tokens: 3459, cost: $0.010377), Output: (tokens: 124, cost: $0.001860)
  FinalCost: $0.012237 (input_cost + output_cost)

Now let me convert 7°C to Fahrenheit:
Tool #2: temperature_converter
[Cycle 2]
  Input: (tokens: 22, cost: $0.000066), Output: (tokens: 105, cost: $0.001575)
  CacheRead: (tokens: 0, cost: $0.000000), CacheWrite: (tokens: 3574, cost: $0.013402)
  FinalCost: $0.015043 (input_cost + output_cost + cache_read_cost + cache_write_cost)
  NetSavings: $-0.002680 (cache_read_benefit - cache_write_penalty)

Now let me multiply 44.6 by 60:
Tool #3: calculator
[Cycle 3]
  Input: (tokens: 26, cost: $0.000078), Output: (tokens: 71, cost: $0.001065)
  CacheRead: (tokens: 3574, cost: $0.001072), CacheWrite: (tokens: 118, cost: $0.000442)
  FinalCost: $0.002658 (input_cost + output_cost + cache_read_cost + cache_write_cost)
  NetSavings: $0.009561 (cache_read_benefit - cache_write_penalty)

Finally, let me convert 2676°F to Celsius:
Tool #4: temperature_converter
[Cycle 4]
  Input: (tokens: 25, cost: $0.000075), Output: (tokens: 107, cost: $0.001605)
  CacheRead: (tokens: 3692, cost: $0.001108), CacheWrite: (tokens: 88, cost: $0.000330)
  FinalCost: $0.003118 (input_cost + output_cost + cache_read_cost + cache_write_cost)
  NetSavings: $0.009902 (cache_read_benefit - cache_write_penalty)

**Results:**
1. 2 + 5 = **7**
2. 7°C = **44.6°F**
3. 44.6 × 60 = **2676**
4. 2676°F = **1468.9°C**

The final answer is **1468.9°C**
[Cycle 5]
  Input: (tokens: 27, cost: $0.000081), Output: (tokens: 82, cost: $0.001230)
  CacheRead: (tokens: 3780, cost: $0.001134), CacheWrite: (tokens: 123, cost: $0.000461)
  FinalCost: $0.002906 (input_cost + output_cost + cache_read_cost + cache_write_cost)
  NetSavings: $0.010114 (cache_read_benefit - cache_write_penalty)


=== Final Summary ===
[Total Tokens] Input: 3559, Output: 489
[Total Cache] Read: 11046, Write: 3903
[Total Cost] $0.035962
[Total Net Savings] $0.026897
```

## Cache Behavior

```
Cycle 1: [System Prompt + Tools + User1] → Assistant1
    └─> Cache Write: 0 (nothing to cache yet)

Cycle 2: Cache Read: 0, Cache Write: 3574
    └─> Writing to cache: [System Prompt + Tools + User1 + Asst1]
        (nothing to read yet, first cache creation)

  Cycle 3: Cache Read: 3574, Cache Write: 118
    └─> Reading from cache: [System Prompt + Tools + User1 + Asst1] = 3574 tokens
    └─> Writing to cache: [User2 + Asst2] = 118 tokens (only the new exchange)

  Cycle 4: Cache Read: 3692, Cache Write: 88
    └─> Reading from cache: [System + Tools + User1 + Asst1 + User2 + Asst2] = 3574 + 118 = 3692 tokens
    └─> Writing to cache: [User3 + Asst3] = 88 tokens (only the new exchange)

  Cycle 5: Cache Read: 3780, Cache Write: 123
    └─> Reading from cache: [System + Tools + User1 + Asst1 + User2 + Asst2 + User3 + Asst3] = 3692 + 88 = 3780 tokens
    └─> Writing to cache: [User4 + Asst4] = 123 tokens (only the new exchange)
```

**How it works:**
- Bedrock waits until there's a meaningful conversation prefix before caching (typically after first exchange)
- Once cached, the prefix (system prompt + early conversation) is reused at 90% discount
- New turns get incrementally added to the cache for future requests

### What Content Is Cached (Claude Models)

With `CacheConfig(strategy="auto")`, Bedrock automatically caches the following content:

1. **System Prompt** - Your agent's instructions (~200 tokens)

2. **Tool Definitions** - All tool schemas in JSON format (~3000+ tokens)
   - Example: `calculator`, `temperature_converter`, `shell`, `editor`
   - Tool schemas are verbose and make up the bulk of initial cache writes

3. **Conversation History** - Previous user and assistant messages

4. **Cache Points** - Automatically placed after each assistant message
   - [Strands: Auto cache strategy](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/model-providers/amazon-bedrock/#messages-caching/)


**Why Cycle 2 cache write is large (3575 tokens):**
- System prompt: ~200 tokens
- 4 tool definitions: ~3000 tokens (tools have extensive JSON schemas)
- First exchange: ~375 tokens
- **Total: ~3575 tokens**

**Important Notes:**
- ✅ **Claude models:** Support caching of system, tools, and messages
- ❌ **Amazon Nova:** Does not support tool caching ([Nova limitations](https://github.com/strands-agents/sdk-python/issues/449))

### Key Points

- **Cache Write** = INPUT tokens being cached (not output) ([AWS docs](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_TokenUsage.html))
- **Cache Read** = INPUT tokens retrieved from cache ([AWS docs](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_TokenUsage.html))
- **TTL**: 5 minutes default, 1 hour available for Claude 4.5 models ([AWS announcement](https://aws.amazon.com/about-aws/whats-new/2026/01/amazon-bedrock-one-hour-duration-prompt-caching/))
- **Cache scope**: Session-isolated - each agent restart creates a new session ID, preventing cache leakage between users/conversations ([Strands: Session Management](https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/session-management/))
- **First call**: No cache benefits (setup phase)
- **Subsequent calls**: Cost savings on cached input within the same session
- **Minimum tokens to cache**: ~1024 tokens (Bedrock won't cache smaller prefixes)
- **Maximum checkpoints**: 4 cache checkpoints per conversation

### Token Accounting: How Input Tokens and Cache Tokens Relate

**Critical Fact:** `inputTokens` **excludes** `cacheReadInputTokens`. They are separate, non-overlapping fields in the AWS Bedrock response.

#### Identical Workload Without vs. With Caching

**Run 1 - WITHOUT Caching (cache_config disabled):**
```
I'll help you with this calculation step by step.

1. First, let me add 2 + 5
2. Then convert that result from Celsius to Fahrenheit
3. Multiply that Fahrenheit value by 60
4. Finally convert that result back to Celsius
Tool #1: calculator
[Cycle 1]
  Input: (tokens: 3459, cost: $0.010377), Output: (tokens: 119, cost: $0.001785)
  FinalCost: $0.012162 (input_cost + output_cost)

Now let me convert 7°C to Fahrenheit:
Tool #2: temperature_converter
[Cycle 2]
  Input: (tokens: 3591, cost: $0.010773), Output: (tokens: 105, cost: $0.001575)
  FinalCost: $0.012348 (input_cost + output_cost)

Now let me multiply 44.6 by 60:
Tool #3: calculator
[Cycle 3]
  Input: (tokens: 3713, cost: $0.011139), Output: (tokens: 71, cost: $0.001065)
  FinalCost: $0.012204 (input_cost + output_cost)

Finally, let me convert 2676°F back to Celsius:
Tool #4: temperature_converter
[Cycle 4]
  Input: (tokens: 3800, cost: $0.011400), Output: (tokens: 108, cost: $0.001620)
  FinalCost: $0.013020 (input_cost + output_cost)

## Results:
1. **2 + 5 = 7**
2. **7°C = 44.6°F**
3. **44.6 × 60 = 2676**
4. **2676°F = 1468.9°C**

The final answer is **1468.9°C**.
[Cycle 5]
  Input: (tokens: 3926, cost: $0.011778), Output: (tokens: 82, cost: $0.001230)
  FinalCost: $0.013008 (input_cost + output_cost)


=== Final Summary ===
[Total Tokens] Input: 18489, Output: 485
[Total Cache] Read: 0, Write: 0
[Total Cost] $0.062742
```

**Run 2 - WITH Caching (`cache_config=CacheConfig(strategy="auto")`):**
```
I'll help you with this calculation. Let me break it down:
1. Add 2 + 5
2. Treat the result as Celsius and convert to Fahrenheit
3. Multiply that Fahrenheit value by 60
4. Convert the result back to Celsius

Let me start:
Tool #1: calculator
[Cycle 1]
  Input: (tokens: 3459, cost: $0.010377), Output: (tokens: 124, cost: $0.001860)
  FinalCost: $0.012237 (input_cost + output_cost)

Now let me convert 7°C to Fahrenheit:
Tool #2: temperature_converter
[Cycle 2]
  Input: (tokens: 22, cost: $0.000066), Output: (tokens: 105, cost: $0.001575)
  CacheRead: (tokens: 0, cost: $0.000000), CacheWrite: (tokens: 3574, cost: $0.013402)
  FinalCost: $0.015043 (input_cost + output_cost + cache_read_cost + cache_write_cost)
  NetSavings: $-0.002680 (cache_read_benefit - cache_write_penalty)

Now let me multiply 44.6 by 60:
Tool #3: calculator
[Cycle 3]
  Input: (tokens: 26, cost: $0.000078), Output: (tokens: 71, cost: $0.001065)
  CacheRead: (tokens: 3574, cost: $0.001072), CacheWrite: (tokens: 118, cost: $0.000442)
  FinalCost: $0.002658 (input_cost + output_cost + cache_read_cost + cache_write_cost)
  NetSavings: $0.009561 (cache_read_benefit - cache_write_penalty)

Finally, let me convert 2676°F to Celsius:
Tool #4: temperature_converter
[Cycle 4]
  Input: (tokens: 25, cost: $0.000075), Output: (tokens: 107, cost: $0.001605)
  CacheRead: (tokens: 3692, cost: $0.001108), CacheWrite: (tokens: 88, cost: $0.000330)
  FinalCost: $0.003118 (input_cost + output_cost + cache_read_cost + cache_write_cost)
  NetSavings: $0.009902 (cache_read_benefit - cache_write_penalty)

**Results:**
1. 2 + 5 = **7**
2. 7°C = **44.6°F**
3. 44.6 × 60 = **2676**
4. 2676°F = **1468.9°C**

The final answer is **1468.9°C**
[Cycle 5]
  Input: (tokens: 27, cost: $0.000081), Output: (tokens: 82, cost: $0.001230)
  CacheRead: (tokens: 3780, cost: $0.001134), CacheWrite: (tokens: 123, cost: $0.000461)
  FinalCost: $0.002906 (input_cost + output_cost + cache_read_cost + cache_write_cost)
  NetSavings: $0.010114 (cache_read_benefit - cache_write_penalty)


=== Final Summary ===
[Total Tokens] Input: 3559, Output: 489
[Total Cache] Read: 11046, Write: 3903
[Total Cost] $0.035962
[Total Net Savings] $0.026897
```

#### Analysis

**Token verification:**
```
Run 1: input (no cache) = 18,489 tokens
Run 2: input + cache_read + cache_write = 3,559 + 11,046 + 3,903 = 18,508 tokens
Difference: 19 tokens
```

**Cost verification:**
```
Run 1: Total Cost = $0.062742
Run 2: Total Cost + Net Savings = $0.035962 + $0.026897 = $0.062859
Difference: $0.00117 (given there is a token deviation of 19 tokens)
```

**What this proves:**
- When caching is enabled, only **new/unique tokens** are counted as `inputTokens`
- **Cached tokens** are tracked separately in `cacheReadInputTokens`
- Without caching, **all tokens** are processed as `inputTokens`
- The token counts match: `input + cache_read + cache_write ≈ total input without cache`

### Cache Invalidation

Cache breaks when:
- **TTL expires** (5 minutes or 1 hour)
- **System prompt changes**
- **Tool definitions change**
- **Conversation manager trims old messages**
- **Agent restarts** - each restart creates a new session ID, isolating cache

**To enable cache persistence across restarts:**
```python
from strands.session.file_session_manager import FileSessionManager

session_manager = FileSessionManager(session_id="persistent-session-id")
agent = Agent(
    model=BedrockModel(...),
    session_manager=session_manager,  # Reuse same session across restarts
    ...
)
```
([Strands: Session Persistence](https://dev.to/aws/til-strands-agents-has-built-in-session-persistence-3nhl))

## Resources

- [Amazon Bedrock Prompt Caching - SimpleAWS Newsletter](https://newsletter.simpleaws.dev/p/amazon-bedrock-prompt-caching)

## License

MIT

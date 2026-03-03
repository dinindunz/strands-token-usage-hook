"""
Token tracking hook for monitoring token usage per cycle and cumulatively.

Tracks input/output tokens, cache read/write tokens, and detailed metrics for each
agent cycle. See README.md for implementation details.
"""

from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import BeforeModelCallEvent, AfterInvocationEvent
from config import MODEL_PRICING


class TokenUsageTracker(HookProvider):
    """
    Hook provider that tracks token usage per cycle.

    Monitors per-cycle and cumulative:
    - Input/output tokens
    - Cache read/write tokens
    """

    def __init__(self, model_id: str):
        """Initialize token tracking hooks."""
        self.model_id = model_id
        self.pricing = MODEL_PRICING.get(model_id, {})
        self.previous_total_input = 0
        self.previous_total_output = 0
        self.previous_cache_read = 0
        self.previous_cache_write = 0
        self.cycle_count = 0
        self.cycle_metrics = []

    def _calculate_cost(self, input_tokens: int, output_tokens: int,
                       cache_read: int, cache_write: int) -> float:
        """Calculate cost in USD for given token counts."""
        if not self.pricing:
            return 0.0

        cost = (
            (input_tokens / 1000) * self.pricing.get("input", 0) +
            (output_tokens / 1000) * self.pricing.get("output", 0) +
            (cache_read / 1000) * self.pricing.get("cache_read", 0) +
            (cache_write / 1000) * self.pricing.get("cache_write", 0)
        )
        return cost

    def _calculate_cache_savings(self, cache_read: int) -> float:
        """Calculate savings from cache reads (vs. regular input tokens)."""
        if not self.pricing or cache_read == 0:
            return 0.0

        input_price = self.pricing.get("input", 0)
        cache_read_price = self.pricing.get("cache_read", 0)
        savings = (cache_read / 1000) * (input_price - cache_read_price)
        return savings

    def register_hooks(self, registry: HookRegistry) -> None:
        """Register hooks for model call events."""
        registry.add_callback(BeforeModelCallEvent, self.track_token_usage)
        registry.add_callback(AfterInvocationEvent, self.track_final_usage)

    def track_token_usage(self, event: BeforeModelCallEvent) -> None:
        """Track token usage from accumulated metrics of completed cycles."""
        agent = event.agent
        current_metrics = agent.event_loop_metrics.accumulated_usage

        current_total_input = current_metrics.get("inputTokens", 0)
        current_total_output = current_metrics.get("outputTokens", 0)
        current_cache_read = current_metrics.get("cacheReadInputTokens", 0)
        current_cache_write = current_metrics.get("cacheWriteInputTokens", 0)

        cycle_input_tokens = current_total_input - self.previous_total_input
        cycle_output_tokens = current_total_output - self.previous_total_output
        cycle_cache_read = current_cache_read - self.previous_cache_read
        cycle_cache_write = current_cache_write - self.previous_cache_write

        self.cycle_count += 1

        # BeforeModelCall fires before cycle N starts, but accumulated_usage contains
        # data from completed cycles (1 through N-1). So we log cycle N-1 here.
        # Skip when display_cycle=0 (first call, no completed cycles yet).
        display_cycle = self.cycle_count - 1

        if display_cycle > 0:
            cycle_cost = self._calculate_cost(
                cycle_input_tokens, cycle_output_tokens,
                cycle_cache_read, cycle_cache_write
            )
            cycle_savings = self._calculate_cache_savings(cycle_cache_read)

            cycle_data = {
                "cycle": display_cycle,
                "input_tokens_this_cycle": cycle_input_tokens,
                "output_tokens_this_cycle": cycle_output_tokens,
                "cache_read_this_cycle": cycle_cache_read,
                "cache_write_this_cycle": cycle_cache_write,
                "cost_this_cycle": cycle_cost,
                "savings_this_cycle": cycle_savings,
            }
            self.cycle_metrics.append(cycle_data)

            savings_str = f", Saved: ${cycle_savings:.6f}" if cycle_savings > 0 else ""
            print(f"[Cycle {display_cycle}] Input: {cycle_input_tokens}, Output: {cycle_output_tokens}, Cache Read: {cycle_cache_read}, Cache Write: {cycle_cache_write}, Cost: ${cycle_cost:.6f}{savings_str}\n")            

        self.previous_total_input = current_total_input
        self.previous_total_output = current_total_output
        self.previous_cache_read = current_cache_read
        self.previous_cache_write = current_cache_write

    def track_final_usage(self, event: AfterInvocationEvent) -> None:
        """Capture the last cycle's tokens that weren't logged by BeforeModelCallEvent."""
        result = event.result
        final_usage = result.metrics.accumulated_usage

        last_cycle_input = final_usage['inputTokens'] - self.previous_total_input
        last_cycle_output = final_usage['outputTokens'] - self.previous_total_output
        last_cycle_cache_read = final_usage.get('cacheReadInputTokens', 0) - self.previous_cache_read
        last_cycle_cache_write = final_usage.get('cacheWriteInputTokens', 0) - self.previous_cache_write

        last_cycle_cost = self._calculate_cost(
            last_cycle_input, last_cycle_output,
            last_cycle_cache_read, last_cycle_cache_write
        )
        last_cycle_savings = self._calculate_cache_savings(last_cycle_cache_read)

        total_cost = self._calculate_cost(
            final_usage['inputTokens'], final_usage['outputTokens'],
            final_usage.get('cacheReadInputTokens', 0),
            final_usage.get('cacheWriteInputTokens', 0)
        )
        total_savings = self._calculate_cache_savings(
            final_usage.get('cacheReadInputTokens', 0)
        )

        cycle_data = {
            "cycle": self.cycle_count,
            "input_tokens_this_cycle": last_cycle_input,
            "output_tokens_this_cycle": last_cycle_output,
            "cache_read_this_cycle": last_cycle_cache_read,
            "cache_write_this_cycle": last_cycle_cache_write,
            "cost_this_cycle": last_cycle_cost,
            "savings_this_cycle": last_cycle_savings,
        }
        self.cycle_metrics.append(cycle_data)

        savings_str = f", Saved: ${last_cycle_savings:.6f}" if last_cycle_savings > 0 else ""
        print(f"\n[Cycle {self.cycle_count}] Input: {last_cycle_input}, Output: {last_cycle_output}, Cache Read: {last_cycle_cache_read}, Cache Write: {last_cycle_cache_write}, Cost: ${last_cycle_cost:.6f}{savings_str}")
        print(f"\n[Total] Input: {final_usage['inputTokens']}, Output: {final_usage['outputTokens']}, Total: {final_usage['totalTokens']}")
        print(f"[Total Cache] Read: {final_usage.get('cacheReadInputTokens', 0)}, Write: {final_usage.get('cacheWriteInputTokens', 0)}")
        print(f"[Total Cost] ${total_cost:.6f}")
        print(f"[Total Savings] ${total_savings:.6f}\n")

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


    def _calculate_cache_savings(self, cache_read: int, cache_write: int) -> float:
        """
        Calculate net savings from caching.

        Net savings = Cache read benefit - Cache write penalty
        - Cache reads save 90% vs regular input ($0.0003 vs $0.003)
        - Cache writes cost 25% more than regular input ($0.00375 vs $0.003)
        """
        if not self.pricing:
            return 0.0

        input_price = self.pricing.get("input", 0)
        cache_read_price = self.pricing.get("cache_read", 0)
        cache_write_price = self.pricing.get("cache_write", 0)

        # Savings from cache reads (vs. regular input)
        read_benefit = (cache_read / 1000) * (input_price - cache_read_price)

        # Penalty from cache writes (extra cost vs. regular input)
        write_penalty = (cache_write / 1000) * (cache_write_price - input_price)

        # Net savings
        net_savings = read_benefit - write_penalty
        return net_savings

    def _calculate_individual_costs(
        self, input_tokens: int, output_tokens: int, cache_read: int, cache_write: int
    ) -> dict:
        """Calculate individual costs for each token type and total cost."""
        if not self.pricing:
            return {
                "input": 0.0,
                "output": 0.0,
                "cache_read": 0.0,
                "cache_write": 0.0,
                "total": 0.0,
            }

        input_cost = (input_tokens / 1000) * self.pricing.get("input", 0)
        output_cost = (output_tokens / 1000) * self.pricing.get("output", 0)
        cache_read_cost = (cache_read / 1000) * self.pricing.get("cache_read", 0)
        cache_write_cost = (cache_write / 1000) * self.pricing.get("cache_write", 0)

        return {
            "input": input_cost,
            "output": output_cost,
            "cache_read": cache_read_cost,
            "cache_write": cache_write_cost,
            "total": input_cost + output_cost + cache_read_cost + cache_write_cost,
        }

    def _print_cycle_details(
        self,
        cycle_num: int,
        input_tokens: int,
        output_tokens: int,
        cache_read: int,
        cache_write: int,
        costs: dict,
        total_cost: float,
        savings: float,
    ) -> None:
        """Print detailed breakdown for a cycle."""
        print(f"[Cycle {cycle_num}]")
        print(
            f"  Input: (tokens: {input_tokens}, cost: ${costs['input']:.6f}), Output: (tokens: {output_tokens}, cost: ${costs['output']:.6f})"
        )

        if cache_read > 0 or cache_write > 0:
            print(
                f"  CacheRead: (tokens: {cache_read}, cost: ${costs['cache_read']:.6f}), CacheWrite: (tokens: {cache_write}, cost: ${costs['cache_write']:.6f})"
            )
            print(
                f"  FinalCost: ${total_cost:.6f} (input_cost + output_cost + cache_read_cost + cache_write_cost)"
            )
            if savings != 0:
                print(
                    f"  NetSavings: ${savings:.6f} (cache_read_benefit - cache_write_penalty)"
                )
        else:
            print(f"  FinalCost: ${total_cost:.6f} (input_cost + output_cost)")
        print()

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
            costs = self._calculate_individual_costs(
                cycle_input_tokens,
                cycle_output_tokens,
                cycle_cache_read,
                cycle_cache_write,
            )
            cycle_cost = costs["total"]
            cycle_savings = self._calculate_cache_savings(
                cycle_cache_read, cycle_cache_write
            )

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

            self._print_cycle_details(
                display_cycle,
                cycle_input_tokens,
                cycle_output_tokens,
                cycle_cache_read,
                cycle_cache_write,
                costs,
                cycle_cost,
                cycle_savings,
            )

        self.previous_total_input = current_total_input
        self.previous_total_output = current_total_output
        self.previous_cache_read = current_cache_read
        self.previous_cache_write = current_cache_write

    def track_final_usage(self, event: AfterInvocationEvent) -> None:
        """Capture the last cycle's tokens that weren't logged by BeforeModelCallEvent."""
        result = event.result
        final_usage = result.metrics.accumulated_usage

        last_cycle_input = final_usage["inputTokens"] - self.previous_total_input
        last_cycle_output = final_usage["outputTokens"] - self.previous_total_output
        last_cycle_cache_read = (
            final_usage.get("cacheReadInputTokens", 0) - self.previous_cache_read
        )
        last_cycle_cache_write = (
            final_usage.get("cacheWriteInputTokens", 0) - self.previous_cache_write
        )

        costs = self._calculate_individual_costs(
            last_cycle_input,
            last_cycle_output,
            last_cycle_cache_read,
            last_cycle_cache_write,
        )
        last_cycle_cost = costs["total"]
        last_cycle_savings = self._calculate_cache_savings(
            last_cycle_cache_read, last_cycle_cache_write
        )

        total_costs = self._calculate_individual_costs(
            final_usage["inputTokens"],
            final_usage["outputTokens"],
            final_usage.get("cacheReadInputTokens", 0),
            final_usage.get("cacheWriteInputTokens", 0),
        )
        total_cost = total_costs["total"]
        total_savings = self._calculate_cache_savings(
            final_usage.get("cacheReadInputTokens", 0),
            final_usage.get("cacheWriteInputTokens", 0),
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

        print()  # Empty line before final cycle
        self._print_cycle_details(
            self.cycle_count,
            last_cycle_input,
            last_cycle_output,
            last_cycle_cache_read,
            last_cycle_cache_write,
            costs,
            last_cycle_cost,
            last_cycle_savings,
        )

        # Print summary
        print(f"\n=== Final Summary ===")
        print(
            f"[Total Tokens] Input: {final_usage['inputTokens']}, Output: {final_usage['outputTokens']}"
        )
        print(
            f"[Total Cache] Read: {final_usage.get('cacheReadInputTokens', 0)}, Write: {final_usage.get('cacheWriteInputTokens', 0)}"
        )
        print(f"[Total Cost] ${total_cost:.6f}")
        if total_savings != 0:
            print(f"[Total Net Savings] ${total_savings:.6f}")
        print()

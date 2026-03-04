"""Pricing configuration for token usage tracking."""

# Pricing per 1K tokens in USD
MODEL_PRICING = {
    "au.anthropic.claude-sonnet-4-5-20250929-v1:0": {
        "input": 0.003,  # $3 per 1M tokens
        "output": 0.015,  # $15 per 1M tokens
        "cache_write": 0.00375,  # $3.75 per 1M tokens (1.25x input - 25% premium for caching overhead)
        "cache_read": 0.0003,  # $0.30 per 1M tokens (0.1x input - 90% discount!)
    }
}


from collections import defaultdict
from datetime import datetime, timedelta

# Define tier-based limits
tier_limits = {
    "free-tier": {"rpm": 5, "tpm": 100},  # Free tier: 5 RPM, 100 TPM
    "paid-tier": {"rpm": 50, "tpm": 1000}  # Paid tier: 50 RPM, 1000 TPM
}

# Map users to tiers
user_to_tier = {
    "user123": "free-tier",
    "user456": "paid-tier"
}

# In-memory storage for request counts
request_counts = defaultdict(list)  # {user_id: [(timestamp, token_count)]}

async def check_rate_limit(user_id, tier, model):
    now = datetime.now()
    limits = tier_limits.get(tier, tier_limits["free-tier"])  # Default to free-tier
    rpm_limit = limits["rpm"]
    tpm_limit = limits["tpm"]

    # Clean up old requests (older than 60 seconds)
    request_counts[user_id] = [
        (ts, tokens) for ts, tokens in request_counts[user_id]
        if now - ts < timedelta(seconds=60)
    ]

    # Count requests and tokens in the last 60 seconds
    recent_requests = len(request_counts[user_id])
    recent_tokens = sum(tokens for _, tokens in request_counts[user_id])

    if recent_requests >= rpm_limit:
        raise Exception(f"Rate limit exceeded for {user_id} (tier: {tier}): {recent_requests}/{rpm_limit} RPM")
    if recent_tokens >= tpm_limit:
        raise Exception(f"Token limit exceeded for {user_id} (tier: {tier}): {recent_tokens}/{tpm_limit} TPM")

    # Estimate token count (simplified; use litellm.token_counter for accuracy)
    token_count = 10  # Placeholder; replace with actual token counting
    request_counts[user_id].append((now, token_count))
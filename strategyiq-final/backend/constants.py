from enum import Enum

SEC_DISCLAIMER = "Financial information only, not financial advice"


class UserTier(str, Enum):
    BEGINNER = "beginner"
    PRO = "pro"
    ELITE = "elite"


TIER_LIMITS = {
    UserTier.BEGINNER: {
        "queries_per_day": 3,
        "realtime": False,
        "signals": False,
        "port_analytics": False,
        "custom_agents": False,
        "model": "gpt-4o-mini",
    },
    UserTier.PRO: {
        "queries_per_day": None,
        "realtime": True,
        "signals": True,
        "port_analytics": False,
        "custom_agents": False,
        "model": "gpt-4o",
    },
    UserTier.ELITE: {
        "queries_per_day": None,
        "realtime": True,
        "signals": True,
        "port_analytics": True,
        "custom_agents": True,
        "model": "claude-3-5-sonnet-20241022",
    },
}

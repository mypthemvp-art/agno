from enum import Enum


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
    },
    UserTier.PRO: {
        "queries_per_day": None,  # unlimited
        "realtime": True,
        "signals": True,
        "port_analytics": False,
        "custom_agents": False,
    },
    UserTier.ELITE: {
        "queries_per_day": None,
        "realtime": True,
        "signals": True,
        "port_analytics": True,
        "custom_agents": True,
    },
}

SEC_DISCLAIMER = "Financial information only, not financial advice"

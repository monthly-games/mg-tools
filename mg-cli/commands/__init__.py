"""
MG-CLI Commands

Command modules for Firebase, Ads, CI/CD, Infrastructure, and Batch operations
"""

from .analytics import analytics, marketing
from .cicd import cicd
from .infra import infra

analytics_cmd = analytics
cicd_cmd = cicd
infra_cmd = infra

__all__ = [
    'analytics',
    'analytics_cmd',
    'marketing',
    'cicd',
    'cicd_cmd',
    'infra',
    'infra_cmd',
]

"""
Placeholder module for financial/business metric calculations.

This module will hold reusable analytical functions (e.g., variance
analysis, growth rates, ratio calculations) used across future
assignments and the final portfolio project.
"""
from __future__ import annotations


def variance_pct(actual: float, budget: float) -> float:
    """
    Calculate percentage variance of actual vs. budget.

    Args:
        actual: Actual value (e.g., actual spend or revenue).
        budget: Budgeted/planned value.

    Returns:
        Percentage variance as a float (e.g., 0.05 for +5%).

    Raises:
        ValueError: If budget is zero.
    """
    if budget == 0:
        raise ValueError("budget must be non-zero to compute variance")
    return (actual - budget) / budget

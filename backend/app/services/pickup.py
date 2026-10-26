"""Pickup point service — list and lookup."""

from __future__ import annotations

from datetime import date

from app.data.interfaces import IParcelRepository
from app.models.parcel import PickupPoint


def list_pickup_points(
    repo: IParcelRepository,
    open_on: date | None = None,
) -> list[PickupPoint]:
    """Return all pickup points, optionally filtered by open day.

    Args:
        repo: The parcel repository.
        open_on: If provided, only return points open on this date.

    Returns:
        A list of ``PickupPoint`` objects.
    """
    all_points = repo.list_pickup_points()
    if open_on is None:
        return all_points
    return [p for p in all_points if p.is_open_on(open_on)]


def get_pickup_point(
    repo: IParcelRepository,
    point_id: str,
) -> PickupPoint | None:
    """Look up a pickup point by ID.

    Returns the ``PickupPoint`` if found, or ``None``.
    """
    return repo.get_pickup_point(point_id)

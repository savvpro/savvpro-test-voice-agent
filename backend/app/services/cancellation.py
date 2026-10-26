"""Cancellation service — cancel a parcel delivery."""

from __future__ import annotations

from app.data.interfaces import IParcelRepository


def cancel_parcel(
    repo: IParcelRepository,
    tracking_id: str,
) -> bool:
    """Cancel a parcel delivery.

    Calls ``repo.cancel_parcel(tracking_id)`` which also releases the
    current slot atomically inside the repository lock.

    Returns ``True`` on success, ``False`` if the parcel was not found or
    already cancelled.
    """
    return repo.cancel_parcel(tracking_id)

"""Verification service — tracking ID lookup and phone verification."""

from __future__ import annotations

from app.data.interfaces import IParcelRepository
from app.models.parcel import Parcel


def verify_tracking_id(
    repo: IParcelRepository,
    tracking_id: str,
) -> Parcel | None:
    """Look up a tracking ID in the repository.

    Returns the :class:`Parcel` if found, or ``None``.
    """
    return repo.get_parcel(tracking_id)


def verify_phone(
    repo: IParcelRepository,
    parcel: Parcel,
    last4: str,
) -> bool:
    """Verify the caller's last 4 phone digits against the parcel.

    On failure, increments the per-parcel phone failure counter.
    If the parcel is already locked (too many prior failures), refuses
    immediately without a new attempt.

    Returns ``True`` if the digits match, ``False`` otherwise.
    """
    # Check if parcel is already locked.
    if repo.is_parcel_locked(parcel.tracking_id):
        return False

    if parcel.phone_last4 == last4:
        return True

    # Wrong digits — increment failure counter.
    repo.increment_phone_failures(parcel.tracking_id)
    return False

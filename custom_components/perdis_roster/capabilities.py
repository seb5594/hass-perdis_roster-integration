"""Which data a Perdis portal exposes, so only sensors that can hold a value are created.

Every portal is an INIT installation configured by its transit operator, and operators unlock
different parts of the API. One portal shows the weekend points account, another does not; one
exposes the time and leave accounts, another only the roster. Creating a sensor that the portal
can never fill would only show "unknown" forever.

At setup the integration therefore probes the portal: the client records which pages it could
read (`reachable_pages`), and `detect` combines that with the values the first snapshot actually
contained. The platforms then create only the entities whose capability is present.
"""

from __future__ import annotations

from .models import Snapshot

# Capability keys. A sensor declares the one it needs; it is created only when the key is present.
CAP_ROSTER = "roster"            # the duty roster / calendar is readable
CAP_OVERTIME = "overtime"        # a working-time balance (Zeitkonto) is readable
CAP_VACATION = "vacation"        # remaining leave days are readable
CAP_WEEKEND_POINTS = "weekend_points"    # the weekend points balance is readable
CAP_WEEKEND_AVERAGE = "weekend_average"  # the group average for weekend points is readable
CAP_WEEKEND_FREE = "weekend_free"        # the count of free weekends is readable
CAP_SWAP = "dutyswap"            # the shift-swap page is readable (and can be acted on)

ALL_CAPABILITIES: frozenset[str] = frozenset({
    CAP_ROSTER,
    CAP_OVERTIME,
    CAP_VACATION,
    CAP_WEEKEND_POINTS,
    CAP_WEEKEND_AVERAGE,
    CAP_WEEKEND_FREE,
    CAP_SWAP,
})


def detect(reachable_pages: set[str], snapshot: Snapshot) -> frozenset[str]:
    """The capabilities of a portal, from the pages it served and the first values it returned.

    The roster counts as available as soon as its page is reachable, even on a week that holds no
    duty. Every account value counts as available only when the portal actually returned it, so a
    portal that hides an account never shows an empty sensor for it.
    """
    capabilities: set[str] = set()
    if "roster" in reachable_pages:
        capabilities.add(CAP_ROSTER)
    if "dutyswap" in reachable_pages:
        capabilities.add(CAP_SWAP)

    balances = snapshot.balances
    if balances.overtime_minutes is not None:
        capabilities.add(CAP_OVERTIME)
    if balances.vacation_remaining_days is not None:
        capabilities.add(CAP_VACATION)

    weekend = snapshot.weekend_points
    if weekend.points is not None:
        capabilities.add(CAP_WEEKEND_POINTS)
    if weekend.group_average is not None:
        capabilities.add(CAP_WEEKEND_AVERAGE)
    if weekend.free_weekends is not None:
        capabilities.add(CAP_WEEKEND_FREE)

    return frozenset(capabilities)

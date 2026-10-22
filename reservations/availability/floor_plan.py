"""Static floor plan of the office used by the availability page.

The plan only knows *where* a resource is drawn. Whether it can be booked is
still decided by the services; this module just combines the two so the
template can paint each spot.

Resources that are not listed in ``LAYOUT`` simply do not appear on the plan,
they stay reachable from the list view.
"""

from dataclasses import dataclass

from ..models import Reservation, Resource

#: Size of the SVG canvas the coordinates below refer to.
VIEWBOX = (1000, 640)

DESK_SIZE = (64, 40)
PARKING_SIZE = (84, 116)


@dataclass(frozen=True)
class Placement:
    x: int
    y: int
    width: int
    height: int
    #: Side of the desk the chair stands on ("n" or "s"); parking has none.
    chair: str = ""


def _desk_island(first_number: int, left: int, top: int) -> dict[str, Placement]:
    """Four desks pushed together, two facing two."""
    width, height = DESK_SIZE
    cells = ((0, 0, "n"), (1, 0, "n"), (0, 1, "s"), (1, 1, "s"))
    return {
        f"A{first_number + index:02d}": Placement(left + col * (width + 2), top + row * (height + 2), width, height, chair)
        for index, (col, row, chair) in enumerate(cells)
    }


def _parking_row(names: list[str], left: int, top: int, gap: int = 12) -> dict[str, Placement]:
    width, height = PARKING_SIZE
    return {name: Placement(left + index * (width + gap), top, width, height) for index, name in enumerate(names)}


LAYOUT: dict[str, Placement] = {
    **_desk_island(1, 268, 146),
    **_desk_island(5, 426, 146),
    **_desk_island(9, 584, 146),
    "VED-01": Placement(826, 92, 84, 46, "s"),
    **_parking_row([f"P{index:02d}" for index in range(1, 7)], 48, 476),
    "P-VIP": Placement(848, 476, *PARKING_SIZE),
}

#: Reservations of the current user that already hold the spot for them.
_MINE_STATUSES = (Reservation.Status.CONFIRMED, Reservation.Status.PENDING_APPROVAL)


def floor_plan_spots(resources, available_ids, user_reservations) -> list[dict]:
    """Describe every placed resource with the state it should be drawn in.

    States: ``mine`` (the user holds or requested it), ``free``, ``approval``
    (free, but booking needs a manager) and ``taken``.
    """
    available_ids = set(available_ids)
    mine = {
        reservation.resource_id: reservation
        for reservation in user_reservations
        if reservation.status in _MINE_STATUSES
    }

    spots = []
    for resource in resources:
        placement = LAYOUT.get(resource.name)
        if placement is None:
            continue

        if resource.pk in mine:
            state = "mine"
        elif resource.pk in available_ids:
            state = "approval" if resource.requires_approval else "free"
        else:
            state = "taken"

        spots.append(
            {
                "resource": resource,
                "kind": "parking" if resource.resource_type == Resource.ResourceType.PARKING_SPOT else "desk",
                "state": state,
                "my_reservation": mine.get(resource.pk),
                "x": placement.x,
                "y": placement.y,
                "width": placement.width,
                "height": placement.height,
                "cx": placement.x + placement.width // 2,
                "cy": placement.y + placement.height // 2,
                "chair_y": placement.y - 12 if placement.chair == "n" else placement.y + placement.height + 12,
                "has_chair": bool(placement.chair),
            }
        )
    return spots

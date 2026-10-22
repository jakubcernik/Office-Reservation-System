"""Who may decide about approval requests (D4: one place for the rule)."""

#: Users in this group may decide about reservations that need approval.
MANAGER_GROUP_NAME = "Office Manager"


def user_can_approve(user) -> bool:
    """Office managers are staff accounts or members of the Office Manager group."""
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(user.is_staff or user.is_superuser or user.groups.filter(name=MANAGER_GROUP_NAME).exists())

from django.http import HttpRequest

from .services import user_can_approve


def navigation(request: HttpRequest) -> dict[str, bool]:
    """Expose the manager navigation entry to templates.

    Templates cannot call services, and the rule who counts as a manager should
    live in exactly one place, so it is evaluated here.
    """
    return {"can_approve_requests": user_can_approve(getattr(request, "user", None))}

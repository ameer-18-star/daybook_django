"""
Makes the current user's UserSettings available in every template as
`global_user_settings`, without every single view needing to fetch and
pass it — used by base.html to set the accent-color/card-theme
attributes on <html>, and by nav headers to show the avatar.
"""
from .models import UserSettings


def user_preferences(request):
    if getattr(request, 'user', None) and request.user.is_authenticated:
        return {'global_user_settings': UserSettings.get_for(request.user)}
    return {'global_user_settings': None}

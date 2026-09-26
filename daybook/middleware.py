"""
Without this, browsers are free to serve the back/forward-cache version of
a page instead of asking the server again — which is exactly what makes
clicking "back" after signing out appear to show you still logged in
(the browser is just replaying its cached copy of the page, not actually
re-authenticating you). Setting Cache-Control: no-store forces a real
request every time, so a signed-out session correctly hits login_required
and redirects to the login page instead.

Skips /static/ and /media/ so this doesn't defeat browser caching for
assets that are genuinely safe (and desirable) to cache.
"""


class NoCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith(('/static/', '/media/')):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
        return response

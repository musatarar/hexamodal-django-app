from rest_framework import authentication, exceptions
from django.conf import settings


class TokenAuthentication(authentication.BaseAuthentication):
    HEADER = "AUTH_TOKEN"

    def authenticate(self, request):
        token_received = request.META.get(self.HEADER)
        if not token_received:
            raise exceptions.AuthenticationFailed("No token provided")

        token_expected = settings.AUTH_TOKEN
        if not token_expected:
            raise exceptions.AuthenticationFailed(
                "Internal error: expected token missing from settings"
            )

        if token_received != token_expected:
            raise exceptions.AuthenticationFailed("Invalid token")

        return (None, None)

    def authenticate_header(self, request):
        return "Token"

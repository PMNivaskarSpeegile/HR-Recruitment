import jwt

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from admin_module.models import UserMaster

class JWTAuthentication(BaseAuthentication):

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return None
        
        parts = auth_header.split()

        if len(parts) != 2 or parts[0] != "Bearer":
            raise AuthenticationFailed("Invalid token format.")
        
        token = parts[1]

        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=["HS256"],
            )
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed("Token has expired.")
        except jwt.InvalidTokenError:
            raise AuthenticationFailed("Invalid token.")

        user_id = payload.get("user_id")

        try:
            user = UserMaster.objects.select_related("role").get(user_id=user_id)
        except UserMaster.DoesNotExist:
             raise AuthenticationFailed("User not found.")

        if not user.is_active:
            raise AuthenticationFailed("User account is inactive.")

        return (user, token)

    def authenticate_header(self, request):
        # Without this, DRF has no WWW-Authenticate header to offer and downgrades
        # every AuthenticationFailed (expired/invalid/missing token) from 401 to
        # 403. The frontend's axios interceptor only treats 401 as "session gone
        # → bounce to login", so an expired token would otherwise leave the user
        # stuck on failing requests instead of being redirected to re-login.
        return "Bearer"

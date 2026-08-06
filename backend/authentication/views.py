# Create your views here.
import logging

from django.contrib.auth.hashers import check_password, make_password
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
import jwt
from datetime import datetime, timedelta,timezone
from django.conf import settings
from admin_module.models import UserMaster
from .serializers import LoginSerializer
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema

logger = logging.getLogger("ats")

# A throwaway hash compared against when the username doesn't exist, so an
# unknown user costs the same time as a known one — closing the timing
# side-channel that otherwise reveals which usernames are valid.
_DUMMY_PASSWORD_HASH = make_password("unused-constant-time-placeholder")


def _user_payload(user):
    """Public-facing shape of the authenticated user (same as login returns)."""
    return {
        "user_id": user.user_id,
        "full_name": user.full_name,
        "username": user.username,
        "email": user.email,
        "role": {
            "id": user.role.role_id,
            "code": user.role.role_code,
            "name": user.role.role_name,
        },
    }


class MeView(APIView):
    """Verify the current JWT and return the authenticated user. The frontend
    calls this on startup to confirm a restored session is still valid before
    trusting it (works for any authenticated role)."""
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response(_user_payload(request.user), status=status.HTTP_200_OK)


class LoginView(APIView):
    permission_classes = [AllowAny]
    # Brute-force protection: limited attempts per client (rate set via env).
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses={200: OpenApiTypes.OBJECT})
    def post(self, request):

        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]

        try:
            user = UserMaster.objects.select_related("role").get(username=username)

        except UserMaster.DoesNotExist:
            # Constant-time: still run a hash comparison so an unknown username
            # is indistinguishable (by timing) from a wrong password.
            check_password(password, _DUMMY_PASSWORD_HASH)
            logger.warning("Failed login: unknown username %r", username)
            return Response(
                {"message": "Invalid username or password"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not check_password(password, user.password_hash):
            logger.warning("Failed login: bad password for user %s", user.user_id)
            return Response(
                {"message": "Invalid username or password"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        if not user.is_active:
            logger.warning("Failed login: inactive account %s", user.user_id)
            return Response(
                {"message": "User account is inactive"},
                status=status.HTTP_403_FORBIDDEN,
            )
        logger.info("Login success: user %s (%s)", user.user_id, user.role.role_code)


        payload = {
            "user_id": user.user_id,
            "username": user.username,
            "role": user.role.role_code,
            "exp": datetime.now(timezone.utc) + timedelta(hours=settings.JWT_ACCESS_HOURS),
            "iat": datetime.now(timezone.utc),
        }

        access = jwt.encode(
            payload,
            settings.SECRET_KEY,
            algorithm="HS256",
        )
    
        return Response(
    {
        "message": "Login successful",
        "token": access,
        "user": {
            "user_id": user.user_id,
            "full_name": user.full_name,
            "username": user.username,
            "email": user.email,
            "role": {
                "id": user.role.role_id,
                "code": user.role.role_code,
                "name": user.role.role_name,
            },
        },
    },
    status=status.HTTP_200_OK,
)
"""
drf-spectacular extension so the OpenAPI schema (and Swagger "Authorize"
button) understands our custom JWT auth as HTTP Bearer.
"""
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class JWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "authentication.jwt_authentication.JWTAuthentication"
    name = "BearerAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}

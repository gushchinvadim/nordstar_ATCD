from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenRefreshSerializer


class PasswordAwareRefreshSerializer(TokenRefreshSerializer):
    """A password reset revokes refresh tokens as well as access tokens."""
    def validate(self, attrs):
        refresh = self.token_class(attrs['refresh'])
        JWTAuthentication().get_user(refresh)
        return super().validate(attrs)

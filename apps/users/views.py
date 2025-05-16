import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from drf_spectacular.utils import OpenApiResponse, extend_schema
from google.auth.transport.requests import Request
from google.oauth2 import id_token
from jwt import PyJWKClient
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.serializers import ResetPasswordSerializer, ResetPasswordValidateSerializer

User = get_user_model()


from apps.users.serializers import (
    AppleSignInResponseSerializer,
    AppleSignInSerializer,
    GoogleSignInResponseSerializer,
    GoogleSignInSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)

User = get_user_model()


class UserViewSet(viewsets.GenericViewSet):
    queryset = User.objects.all()

    def get_permissions(self):
        if self.action == 'signup':
            return [permissions.AllowAny()]
        elif self.action == 'me':
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == 'signup':
            return UserRegistrationSerializer
        elif self.action == 'me':
            return UserSerializer
        return UserSerializer

    @action(detail=False, methods=['post'])
    def signup(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({'detail': 'User created successfully.'}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get', 'put', 'patch'])
    def me(self, request):
        if request.method == 'GET':
            serializer = self.get_serializer(request.user)
            return Response(serializer.data)
        else:
            data = request.data.copy()
            password = data.pop('password', None)
            serializer = self.get_serializer(request.user, data=data, partial=True)
            serializer.is_valid(raise_exception=True)
            user = serializer.save()
            if password:
                user.set_password(password)
                user.save()
            return Response(serializer.data)


class GoogleSignInView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=GoogleSignInSerializer,
        responses={
            200: GoogleSignInResponseSerializer,
            400: OpenApiResponse(description="Invalid or missing ID Token."),
        },
        summary="Google OAuth2 Sign-In",
        description="Authenticate a user using a Google OAuth2 ID Token and return JWT tokens.",
    )
    def post(self, request):
        serializer = GoogleSignInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_token_from_frontend = serializer.validated_data.get("idToken")

        try:
            id_info = id_token.verify_oauth2_token(id_token_from_frontend, Request(), settings.GOOGLE_CLIENT_ID)

            email = id_info.get("email")
            given_name = id_info.get("given_name", "")
            family_name = id_info.get("family_name", "")
            if not email:
                return Response({"error": "Invalid ID Token"}, status=status.HTTP_400_BAD_REQUEST)

            user, created = User.objects.get_or_create(
                username=email,
                defaults={"email": email, "first_name": given_name, "last_name": family_name},
            )
            refresh = RefreshToken.for_user(user)

            response_serializer = GoogleSignInResponseSerializer(
                {
                    "accessToken": str(refresh.access_token),
                    "refreshToken": str(refresh),
                    "firstName": user.first_name,
                    "lastName": user.last_name,
                }
            )

            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except ValueError:
            return Response({"error": "Invalid ID Token"}, status=status.HTTP_400_BAD_REQUEST)


def validate_apple_id_token(id_token):
    try:
        jwks_url = "https://appleid.apple.com/auth/keys"
        jwks_client = PyJWKClient(jwks_url)

        signing_key = jwks_client.get_signing_key_from_jwt(id_token)

        decoded_token = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.APPLE_CLIENT_ID,
            issuer="https://appleid.apple.com",
        )

        return decoded_token

    except jwt.ExpiredSignatureError:
        raise ValidationError({"error": "ID Token has expired."})
    except jwt.InvalidTokenError as e:
        raise ValidationError({"error": f"Invalid ID Token: {str(e)}"})


class AppleSignInView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        request=AppleSignInSerializer,
        responses={
            200: AppleSignInResponseSerializer,
            400: OpenApiResponse(description="Invalid or missing ID Token."),
        },
        summary="Apple OAuth2 Sign-In",
        description="Authenticate a user using Apple Sign-In and return JWT tokens.",
    )
    def post(self, request):
        serializer = AppleSignInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        id_token_from_frontend = serializer.validated_data.get("idToken")

        if not id_token_from_frontend:
            raise ValidationError({"error": "ID Token is required."})

        try:
            decoded_id_token = validate_apple_id_token(id_token_from_frontend)

            email = decoded_id_token.get("email")
            user_identifier = decoded_id_token.get("sub")

            if not email:
                return Response({"error": "Email not found in ID Token."}, status=status.HTTP_400_BAD_REQUEST)

            first_name = ""
            last_name = ""

            if 'name' in decoded_id_token:
                name_obj = decoded_id_token.get('name', {})
                if isinstance(name_obj, dict):
                    first_name = name_obj.get('firstName', '')
                    last_name = name_obj.get('lastName', '')

            if not first_name:
                first_name = decoded_id_token.get('given_name', '')
            if not last_name:
                last_name = decoded_id_token.get('family_name', '')

            user, created = User.objects.get_or_create(
                username=user_identifier,
                defaults={
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                },
            )

            if not created and not user.first_name and first_name:
                user.first_name = first_name
                user.last_name = last_name
                user.save()

            refresh = RefreshToken.for_user(user)

            response_serializer = AppleSignInResponseSerializer(
                {
                    "accessToken": str(refresh.access_token),
                    "refreshToken": str(refresh),
                    "firstName": user.first_name,
                    "lastName": user.last_name,
                }
            )

            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except ValidationError as e:
            return Response({"error": e.detail}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordAPIView(GenericAPIView):
    serializer_class = ResetPasswordSerializer
    queryset = User.objects.none()
    permission_classes = (AllowAny,)
    throttle_classes = (AnonRateThrottle,)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.send_mail()
        return Response(status=status.HTTP_200_OK, data={"success": True})


class ResetPasswordValidateAPIView(GenericAPIView):
    serializer_class = ResetPasswordValidateSerializer
    queryset = User.objects.none()
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_200_OK, data={"success": True})

# users/serializers.py

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from apps.users.models import ResetPasswordToken, UserProfile
from apps.users.tasks import task_send_password_reset_email

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True, required=True)
    phone_number = serializers.CharField(required=True)
    password = serializers.CharField(required=True)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone_number', 'password', 'confirm_password')

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email is already registered.")
        return value

    def validate(self, data):
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return data

    def create(self, validated_data):
        phone_number = validated_data.pop('phone_number')
        validated_data.pop('confirm_password')
        email = validated_data['email']

        user = User.objects.create_user(
            username=email,
            email=email,
            password=validated_data['password'],
            first_name=validated_data['first_name'],
            last_name=validated_data['last_name'],
        )
        UserProfile.objects.update_or_create(user=user, phone_number=phone_number)
        return user


class UserSerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(required=False, allow_null=True)
    password = serializers.CharField(write_only=True, required=False, min_length=8)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone_number', 'password')
        extra_kwargs = {'password': {'write_only': True}}

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        try:
            ret['phone_number'] = instance.profile.phone_number
        except UserProfile.DoesNotExist:
            ret['phone_number'] = None
        return ret

    def update(self, instance, validated_data):
        phone_number = validated_data.pop('phone_number', None)

        for attr, value in validated_data.items():
            if attr == 'password':
                instance.set_password(value)
            else:
                setattr(instance, attr, value)
        instance.save()

        if phone_number is not None:
            profile, created = UserProfile.objects.get_or_create(user=instance)
            profile.phone_number = phone_number
            profile.save()

        return instance


class GoogleSignInSerializer(serializers.Serializer):
    idToken = serializers.CharField(required=True, help_text="ID Token received from Google after authentication.")


class GoogleSignInResponseSerializer(serializers.Serializer):
    accessToken = serializers.CharField(read_only=True, help_text="JWT access token for authenticated requests.")
    refreshToken = serializers.CharField(read_only=True, help_text="JWT refresh token to obtain new access tokens.")
    firstName = serializers.CharField()
    lastName = serializers.CharField()


class AppleSignInSerializer(serializers.Serializer):
    idToken = serializers.CharField(required=True, help_text="ID Token from Apple")


class AppleSignInResponseSerializer(serializers.Serializer):
    accessToken = serializers.CharField()
    refreshToken = serializers.CharField()
    firstName = serializers.CharField()
    lastName = serializers.CharField()


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(write_only=True)

    def send_mail(self):
        task_send_password_reset_email.delay(self.validated_data["email"])


class ResetPasswordValidateSerializer(serializers.Serializer):
    token = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)
    password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        try:
            if ResetPasswordToken.objects.get(token=attrs['token']):
                raise serializers.ValidationError({"token": "Token is expired"})
        except ResetPasswordToken.DoesNotExist:
            pass

        try:
            uid, _ = urlsafe_base64_decode(attrs['token']).decode().split(':')
            self.user = User.objects.get(pk=uid)
        except (
            TypeError,
            ValueError,
            OverflowError,
            User.DoesNotExist,
            DjangoValidationError,
        ):
            self.user = None

        if not self.user:
            raise serializers.ValidationError({"token": "Invalid Token"})

        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "Password and Confirm Password do not match"})

        try:
            validate_password(attrs["password"], self.user)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": e.messages})
        return attrs

    def save(self):
        self.user.set_password(self.validated_data["password"])
        self.user.is_active = True
        self.user.save()
        ResetPasswordToken.objects.create(token=self.validated_data["token"])

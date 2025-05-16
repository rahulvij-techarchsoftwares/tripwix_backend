import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.external_apis.pipedrive.sdk import PipedriveAPI

from .models import Inquiry, Lead
from .serializers import InquirySerializer, LeadSerializer, SendEmailCreatePersonSerializer

logger = logging.getLogger(__name__)


class LeadCreateView(CreateAPIView):
    queryset = Lead.objects.all()
    serializer_class = LeadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            {"message": "Thank you for reaching out! We'll contact you soon.", "lead_id": serializer.instance.id},
            status=status.HTTP_200_OK,
        )


class InquiryCreateView(CreateAPIView):
    queryset = Inquiry.objects.all()
    serializer_class = InquirySerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            {"message": "Thank you for reaching out! We'll contact you soon.", "inquiry_id": serializer.instance.id},
            status=status.HTTP_200_OK,
        )


class CreatePersonView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=SendEmailCreatePersonSerializer,
        responses={
            200: OpenApiResponse(
                description="Person created in Pipedrive",
                examples={
                    "application/json": {
                        "message": "Person created in Pipedrive",
                        "pipedrive_person_id": 12345,
                    }
                },
            ),
            400: OpenApiResponse(description="Email field is needed."),
            500: OpenApiResponse(description="Failed to create Person in pipedrive."),
        },
    )
    def post(self, request, format=None):
        serializer = SendEmailCreatePersonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        person_name = f"{email}"
        person_data = {
            'name': person_name,
            'email': [{'value': email, 'primary': True}],
            'marketing_status': 'subscribed',
        }

        pipedrive_api = PipedriveAPI()
        try:
            person_response = pipedrive_api.create_person(person_data)
            if not person_response.get('success'):
                logger.error(f"Failed to create person in Pipedrive: {person_response}")
                return Response(
                    {'error': 'Failed to create person in Pipedrive'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            pipedrive_person_id = person_response['data']['id']
        except Exception as e:
            logger.error(f"Failed to create person in Pipedrive: {e}")
            return Response(
                {'error': 'Failed to create person in Pipedrive'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            {'message': 'Person created in Pipedrive', 'pipedrive_person_id': pipedrive_person_id},
            status=status.HTTP_200_OK,
        )

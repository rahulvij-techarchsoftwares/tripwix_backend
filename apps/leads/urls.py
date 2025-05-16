from django.urls import path

from .views import CreatePersonView, InquiryCreateView, LeadCreateView

urlpatterns = [
    path('leads', LeadCreateView.as_view(), name='lead-create'),
    path('inquires', InquiryCreateView.as_view(), name='inquiry-create'),
    path('create-person/', CreatePersonView.as_view(), name='send_email_create_person'),
]

from rest_framework import serializers

from .models import Inquiry, Lead


class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = (
            'id',
            'src_id',
            'form_id',
            'first_name',
            'last_name',
            'email',
            'phone_number',
            'desired_destination',
            'how_can_we_help',
            'how_can_we_help_extra_field',
            'where_heard_about_us',
            'where_heard_about_us_extra_field',
            'questions_or_comments',
            'newsletter',
            'smsMarketing',
        )

    def validate(self, data):
        where_heard_about_us = data.get('where_heard_about_us')
        where_heard_about_us_extra_field = data.get('where_heard_about_us_extra_field')
        if where_heard_about_us == 'others' and not where_heard_about_us_extra_field:
            raise serializers.ValidationError(
                {
                    'where_heard_about_us_extra_field': 'This field is required when "Others" is selected in "Where heard about us".'
                }
            )

        how_can_we_help = data.get('how_can_we_help')
        how_can_we_help_extra_field = data.get('how_can_we_help_extra_field')
        if how_can_we_help == 'others' and not how_can_we_help_extra_field:
            raise serializers.ValidationError(
                {
                    'how_can_we_help_extra_field': 'This field is required when "Others" is selected in "How can we help".'
                }
            )
        return data


class InquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = Inquiry
        fields = '__all__'


class SendEmailCreatePersonSerializer(serializers.Serializer):
    email = serializers.EmailField()

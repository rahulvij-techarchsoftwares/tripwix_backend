import boto3
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Clean the uploads directory on S3'

    def add_arguments(self, parser):
        parser.add_argument('bucket_name', type=str, help='The S3 bucket name')
        parser.add_argument('uploads_dir', type=str, help='The uploads directory on S3')

    def handle(self, *args, **kwargs):
        bucket_name = kwargs['bucket_name']
        uploads_dir = kwargs['uploads_dir']

        s3 = boto3.resource('s3')
        bucket = s3.Bucket(bucket_name)
        bucket.objects.filter(Prefix=uploads_dir).delete()

        self.stdout.write(
            self.style.SUCCESS(f'Successfully cleaned uploads directory {uploads_dir} in bucket {bucket_name}')
        )

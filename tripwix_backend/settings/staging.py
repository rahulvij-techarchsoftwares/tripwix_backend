import sentry_sdk

from .common import *

CSRF_TRUSTED_ORIGINS = [
    "https://staging.worldeluxevillas.com",
    "https://*.worldeluxevillas.com/",
    # TODO: Remove after initial development
    "http://localhost:3000",
]

CORS_ALLOWED_ORIGINS = [
    "https://staging.worldeluxevillas.com",
    "https://*.worldeluxevillas.com",
    "http://localhost:3000",
]

PREPEND_WWW = False

DEBUG = True
PROJECT_URL = "https://admin-staging.worldeluxevillas.com"
# MEDIA_URL = PROJECT_URL + "/static/"
MEDIA_URL = "https://d1xohhabe9xth2.cloudfront.net/uploads/"

# STORAGES = {
#     "default": {
#         "BACKEND": "storages.backends.s3.S3Storage",
#         "OPTIONS": {
#             "bucket_name": "tripwix-platform",
#             "location": "uploads",
#             "region_name": "eu-west-1",
#             "access_key": "AKIA3BS7ENXSJXZBNEP6",
#             "secret_key": "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",
#             "querystring_auth": False,
#         },
#     },
#     "staticfiles": {
#         "BACKEND": "storages.backends.s3.S3Storage",
#         "OPTIONS": {
#             "bucket_name": "tripwix-platform",
#             "location": "static",
#             "region_name": "eu-west-1",
#             "access_key": "AKIA3BS7ENXSJXZBNEP6",
#             "secret_key": "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",
#         },
#     },
# }

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": "tripwix-platform-media",
            "location": "uploads",
            "region_name": "eu-west-1",
            "access_key": "AKIA3BS7ENXSJXZBNEP6",
            "secret_key": "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",
            "querystring_auth": False,
            "custom_domain": "d1xohhabe9xth2.cloudfront.net",
        },
    },
    "staticfiles": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": "tripwix-platform-media",
            "location": "static",
            "region_name": "eu-west-1",
            "access_key": "AKIA3BS7ENXSJXZBNEP6",
            "secret_key": "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",
            "custom_domain": "d1xohhabe9xth2.cloudfront.net",
        },
    },
}

sentry_sdk.init(
    dsn="https://a9ab8d914850bca643c03a56afd41061@o148064.ingest.sentry.io/4506082991079424",
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    traces_sample_rate=0.25,
    # Set profiles_sample_rate to 1.0 to profile 100%
    # of sampled transactions.
    # We recommend adjusting this value in production.
    profiles_sample_rate=0.1,
    environment="staging",
)

FRONTOFFICE_URL = "https://staging.worldeluxevillas.com"

import sentry_sdk

from .common import *

CSRF_TRUSTED_ORIGINS = [
    "https://*.worldeluxevillas.com/",
    "https://tripwix.com/",
    "https://www.tripwix.com/",
]

CORS_ALLOWED_ORIGINS = [
    "https://staging.worldeluxevillas.com",
    "https://*.worldeluxevillas.com",
    "http://localhost:3000",
    "https://tripwix.com",
    "https://www.tripwix.com",
]
CORS_ALLOW_HEADERS = [
    'accept',
    'authorization',
    'content-type',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'cache-control',
]

# Optional settings
CORS_EXPOSE_HEADERS = []
CORS_PREFLIGHT_MAX_AGE = 86400  # 24 hours

PREPEND_WWW = False

DEBUG = False

ENABLE_BACKOFFICE_IMPORT = True
PROJECT_URL = "https://admin.worldeluxevillas.com"
MEDIA_URL = PROJECT_URL + "/static/"

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
    environment="production",
)

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
FRONTOFFICE_URL = "https://www.tripwix.com/"

EMAIL_HOST = "smtp.sendgrid.net"
EMAIL_PORT = 587
EMAIL_HOST_USER = "apikey"
EMAIL_HOST_PASSWORD = "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"


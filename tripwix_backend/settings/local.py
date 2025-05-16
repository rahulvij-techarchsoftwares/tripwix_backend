from .common import *

DEBUG = True

STATICFILES_DIRS = (
    os.path.join(BASE_DIR, 'upload'),
)
ENABLE_BACKOFFICE_IMPORT = True
UPDATE_FILE_ID = os.getenv("UPDATE_FILE_ID", "1N3o0aNoIXdPN4B0T3mWFoez0gO9GH0DEq1NWpCZGp68")
CORS_ALLOW_ALL_ORIGINS = True
MIDDLEWARE = [
    "kolo.middleware.KoloMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "tripwix_backend.middleware.AjaxMiddleware",
]
SEND_DATA_TO_PIPEDRIVE = False

FRONTOFFICE_URL = "http://localhost:3000"


MEDIA_URL = "https://d1xohhabe9xth2.cloudfront.net/uploads/"

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": "tripwix-platform-media",
            "location": "uploads",
            "region_name": "eu-west-1",
            "access_key": "AKIA3BS7ENXSJXZBNEP6",
            "secret_key": "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",
            "custom_domain": "d1xohhabe9xth2.cloudfront.net",
            "querystring_auth": False,
        },
    },
}


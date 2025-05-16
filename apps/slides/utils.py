from django.core.exceptions import ValidationError


def validate_image_size(image, max_size, verbose_size):
    try:
        if image and image.size > max_size:
            raise ValidationError(f'Image size must be no more than {verbose_size}.')
    except FileNotFoundError:
        pass

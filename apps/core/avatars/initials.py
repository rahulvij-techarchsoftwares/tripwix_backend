from urllib.parse import quote


class InitialsAvatar(object):
    DEFAULT_IMAGE_SIZE = 80
    BACKGROUND_COLORS = [
        '#B2ABF2',
        '#89043D',
        '#2FE6DE',
        '#1C3041',
        '#18F2B2',
        '#040F0F',
        '#2BA84A',
        '#2D3A3A',
        '#074F57',
        '#077187',
        '#74A57F',
        '#9ECE9A',
        '#E4C5AF',
    ]

    def __init__(self, user):
        self.user_name_length = len(user.name)
        self.text = user.initials

    def get_color(self):
        return self.BACKGROUND_COLORS[self.user_name_length % len(self.BACKGROUND_COLORS)]

    def get_image(self, size=DEFAULT_IMAGE_SIZE, background_color=None):
        if background_color is None:
            background_color = self.get_color()

        url = 'data:image/svg+xml,'

        url += quote(
            (
                '<svg viewBox="0 0 160 160" xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}">'
                '<rect width="160" height="160" fill="{background_color}"/>'
                '<text x="50%" y="50%" font-size="42" letter-spacing="2" font-family="Arial, sans-serif" '
                'dy="14" text-anchor="middle" fill="#fff">{text}</text>'
                '</svg>'
            )
            .format(size=size, background_color=background_color, text=self.text)
            .encode('utf8')
        )

        return url

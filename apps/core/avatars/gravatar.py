from hashlib import md5
from urllib.parse import urlencode


class Gravatar(object):
    DEFAULT_IMAGE_SIZE = 80
    DEFAULT_IMAGE = [
        '404',
        'mm',
        'mp',
        'identicon',
        'monsterid',
        'wavatar',
        'retro',
        'robohash',
        'blank',
    ]

    def __init__(self, email):
        self.email = email.lower().strip()
        self.email_hash = md5(self.email.encode('utf-8')).hexdigest()

    def get_image(self, size=DEFAULT_IMAGE_SIZE, default="", filetype_extension=False):
        base_url = '{protocol}://{domain}/avatar/' '{hash}{extension}{params}'

        params_dict = {'size': size, 'default': default}

        if params_dict['size'] == self.DEFAULT_IMAGE_SIZE:
            del params_dict['size']
        else:
            if not (0 < params_dict['size'] < 2048):
                raise ValueError('Invalid image size.')
        if params_dict['default'] == '':
            del params_dict['default']
        else:
            if not params_dict['default'] in self.DEFAULT_IMAGE:
                raise ValueError('Your URL for the default image is not valid.')

        params = urlencode(params_dict)

        use_ssl = True
        protocol = 'http'
        domain = 'www.gravatar.com'
        if use_ssl:
            protocol = 'https'
            domain = 'secure.gravatar.com'

        extension = '.jpg' if filetype_extension else ''
        params = '?%s' % params if params else ''
        data = {
            'protocol': protocol,
            'domain': domain,
            'hash': self.email_hash,
            'extension': extension,
            'params': params,
        }
        return base_url.format(**data)

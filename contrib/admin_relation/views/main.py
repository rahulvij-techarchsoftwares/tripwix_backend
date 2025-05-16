from django.contrib.admin.utils import quote
from django.contrib.admin.views.main import ChangeList


class RelationAdminChangeList(ChangeList):
    def __init__(self, request, *args, **kwargs):
        super(RelationAdminChangeList, self).__init__(request, *args, **kwargs)
        self.request = request

    def url_for_result(self, result):
        pk = getattr(result, self.pk_attname)
        return self.model_admin.reverse_url('change', *self.model_admin.get_base_url_args(self.request) + [quote(pk)])

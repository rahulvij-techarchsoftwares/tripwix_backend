class AdminTestMixin:
    def test_list(self, admin_client):
        self.factory.create_batch(2)
        response = admin_client.get(self.url)

        assert response.status_code == 200
        assert response.context_data["cl"].result_list.count() == 2

    def test_post(self, admin_client):
        url = f"{self.url}add/"
        response = admin_client.post(url, data=self.data)

        assert response.status_code == getattr(self, "post_status_code", 302)
        assert self.model.objects.count() == 1

    def test_update(self, admin_client):
        obj = self.factory()
        url = f"{self.url}{obj.pk}/change/"
        response = admin_client.post(url, data=self.data)

        assert response.status_code == getattr(self, "update_status_code", 302)
        assert self.model.objects.count() == 1

        obj.refresh_from_db()
        for key, value in self.data.items():
            try:
                assert getattr(obj, key).pk == value
            except AttributeError:
                assert getattr(obj, key) == value

    def test_delete(self, admin_client):
        obj = self.factory()
        url = f"{self.url}{obj.pk}/delete/"
        response = admin_client.post(url, data={"post": "yes"})

        assert response.status_code == 302
        assert self.model.objects.count() == 0

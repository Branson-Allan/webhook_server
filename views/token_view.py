from views.base_view import JsonView


class TokenView(JsonView):
    def show(self, issued):
        # `token` and `accessToken` are aliases so CRMs that look for either key still work.
        return self.respond(200, {
            "access_token": issued.value,
            "token": issued.value,
            "accessToken": issued.value,
            "token_type": "Bearer",
            "expires_in": issued.expires_in,
        }, {"Cache-Control": "no-store"})
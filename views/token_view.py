from views.base_view import JsonView


class TokenView(JsonView):
    def show(self, issued):
        return self.respond(200, {
            "access_token": issued.value,
            "token_type": "Bearer",
            "expires_in": issued.expires_in,
        })

"""Cloudflare Python Worker entrypoint."""

try:
    from webhook import handle_request
except ImportError:
    from cloudflare.webhook import handle_request

try:
    from workers import WorkerEntrypoint  # type: ignore
except ImportError:

    class WorkerEntrypoint:  # type: ignore
        pass


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        return await handle_request(request, self.env)

class EchoProcessor:
    def __init__(self, service):
        self.service = service

    def set_parent(self, parent):
        self.parent = parent

    async def __call__(self, frame):
        # Call the wrapped echo_service
        return await self.service(frame)

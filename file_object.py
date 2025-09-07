# Create FileObj class for this context
from io import BytesIO


class FileObject:
    def __init__(self, content, name):
        self.content = BytesIO(content)
        self.name = name
        self.color = None
        self.order_id = None

    def read(self):
        return self.content.read()

    def seek(self, pos):
        return self.content.seek(pos)

"""Bound multipart bytes while receiving them, before storing a complete upload."""

from django.core.exceptions import RequestDataTooBig
from django.core.files.uploadhandler import FileUploadHandler


class UploadBudgetHandler(FileUploadHandler):
    def __init__(self, request, limit):
        super().__init__(request)
        self.limit = limit
        self.received = 0

    def receive_data_chunk(self, raw_data, start):
        self.received += len(raw_data)
        if self.received > self.limit:
            raise RequestDataTooBig("Os arquivos excedem o limite desta operação.")
        return raw_data

    def file_complete(self, file_size):
        return None

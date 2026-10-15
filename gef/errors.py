class AppError(Exception):
    def __init__(self, code, status=400, fields=None):
        self.code, self.status, self.fields = code, status, fields or {}

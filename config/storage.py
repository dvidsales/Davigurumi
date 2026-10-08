"""Private Supabase objects, always served through Django authorization."""

import json
from io import BytesIO
from pathlib import PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import File
from django.core.files.storage import Storage


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class SupabasePrivateStorage(Storage):
    def __init__(self, bucket=None):
        self.bucket = bucket or settings.SUPABASE_FILES_BUCKET
        self.base = settings.SUPABASE_URL.rstrip("/") + "/storage/v1"
        url = urlsplit(settings.SUPABASE_URL)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in ("", "/")
            or not settings.SUPABASE_SERVICE_KEY
        ):
            raise ValidationError(
                "Configure o armazenamento privado HTTPS e sua credencial no servidor."
            )

    @staticmethod
    def name(name):
        name = str(name)
        if (
            not name
            or name.startswith("/")
            or "\\" in name
            or any(p in ("", ".", "..") for p in name.split("/"))
        ):
            raise ValidationError("Caminho de arquivo privado inválido.")
        return name

    def request(self, method, path, data=None, missing=False, upsert=False):
        headers = {
            "Authorization": "Bearer " + settings.SUPABASE_SERVICE_KEY,
            "apikey": settings.SUPABASE_SERVICE_KEY,
        }
        if isinstance(data, dict):
            data = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
        elif data is not None:
            headers["Content-Type"] = "application/octet-stream"
            headers["x-upsert"] = "true" if upsert else "false"
        request = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with build_opener(NoRedirect()).open(request, timeout=15) as response:
                value = response.read(5 * 1024 * 1024 + 1)
                if len(value) > 5 * 1024 * 1024:
                    raise ValidationError("Objeto privado excede o limite permitido.")
                return value
        except HTTPError as exc:
            if missing:
                try:
                    details = json.loads(exc.read(8192))
                except (ValueError, OSError):
                    details = {}
                if (
                    exc.code == 404
                    or isinstance(details, dict)
                    and details.get("code") == "NoSuchKey"
                    or isinstance(details, dict)
                    and str(details.get("statusCode")) == "404"
                ):
                    raise FileNotFoundError from None
            raise ValidationError(
                "Armazenamento privado indisponível; tente novamente ou consulte o responsável."
            ) from None
        except (URLError, TimeoutError, OSError):
            raise ValidationError(
                "Armazenamento privado indisponível; tente novamente ou consulte o responsável."
            ) from None

    def check_private(self):
        try:
            bucket = json.loads(
                self.request("GET", "/bucket/" + quote(self.bucket, safe=""))
            )
            if not isinstance(bucket, dict) or bucket.get("public") is not False:
                raise ValueError
        except (ValueError, TypeError):
            raise ValidationError("O bucket deve existir e ser privado.") from None

    def _open(self, name, mode="rb"):
        if mode not in ("r", "rb"):
            raise ValueError("Leitura de arquivos privados apenas.")
        name = self.name(name)
        self.check_private()
        data = self.request(
            "GET",
            "/object/authenticated/"
            + quote(self.bucket, safe="")
            + "/"
            + quote(name, safe="/"),
            missing=True,
        )
        return File(BytesIO(data), name=name)

    def put(self, name, data, upsert=False):
        name = self.name(name)
        self.check_private()
        self.request(
            "POST",
            "/object/" + quote(self.bucket, safe="") + "/" + quote(name, safe="/"),
            data,
            upsert=upsert,
        )
        return name

    def _save(self, name, content):
        value = content.read(5 * 1024 * 1024 + 1)
        if len(value) > 5 * 1024 * 1024:
            raise ValidationError("Arquivo privado excede 5 MB.")
        return self.put(name, value)

    def exists(self, name):
        try:
            with self._open(name):
                return True
        except FileNotFoundError:
            return False

    def delete(self, name):
        self.check_private()
        self.request(
            "DELETE",
            "/object/" + quote(self.bucket, safe=""),
            {"prefixes": [self.name(name)]},
        )

    def size(self, name):
        with self._open(name) as file:
            return file.size

    def url(self, name):
        raise ValueError("Arquivos privados não possuem URL pública.")

    def listdir(self, path):
        prefix = self.name(path) if path else ""
        self.check_private()
        directories, files, offset = [], [], 0
        while True:
            rows = json.loads(
                self.request(
                    "POST",
                    "/object/list/" + quote(self.bucket, safe=""),
                    {
                        "prefix": prefix,
                        "limit": 1000,
                        "offset": offset,
                        "sortBy": {"column": "name", "order": "asc"},
                    },
                )
            )
            for row in rows:
                name = self.name(row["name"])
                (files if row.get("id") else directories).append(name)
            if len(rows) < 1000:
                return directories, files
            offset += len(rows)

    def walk(self, prefix):
        directories, files = self.listdir(prefix)
        for name in files:
            yield str(PurePosixPath(prefix) / name)
        for name in directories:
            yield from self.walk(str(PurePosixPath(prefix) / name))

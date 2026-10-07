#!/usr/bin/env bash
set -euo pipefail
cd /workspace/Davigurumi
umask 077
destination="${1:?Informe um diretório novo para o backup.}"
if [ -e "$destination" ]; then echo 'O destino já existe; nenhuma cópia foi sobrescrita.' >&2; exit 1; fi
mkdir -p "$destination"
docker exec davigurumi-postgres pg_dump -U davigurumi -d "${DAVIGURUMI_TEST_DB:-davigurumi}" --format=custom > "$destination/database.dump"
/workspace/.venvs/davigurumi/bin/python - "$destination" <<'PY'
import hashlib, json, sys, zipfile, os
from pathlib import Path
from datetime import datetime, timezone
p=Path(sys.argv[1])
manifest={'version':1, 'created_at':datetime.now(timezone.utc).isoformat(), 'database_sha256':hashlib.sha256((p/'database.dump').read_bytes()).hexdigest(), 'scope':'development-postgresql-database'}
media=Path(os.environ.get('DJANGO_MEDIA_ROOT','.local/files')).resolve();manifest['files']={}
with zipfile.ZipFile(p/'files.zip','w',compression=zipfile.ZIP_DEFLATED) as archive:
 if media.exists():
  for file in sorted(media.rglob('*')):
   if file.is_file():
    if not file.resolve().is_relative_to(media): raise SystemExit('Arquivo privado fora da raiz esperada.')
    name=file.relative_to(media).as_posix()
    manifest['files'][name]=hashlib.sha256(file.read_bytes()).hexdigest();archive.write(file,name)
manifest['files_archive_sha256']=hashlib.sha256((p/'files.zip').read_bytes()).hexdigest()
(p/'manifest.json').write_text(json.dumps(manifest,indent=2))
print('Backup local concluído; banco, objetos privados e manifesto criados. Não substitui destino independente.')
PY

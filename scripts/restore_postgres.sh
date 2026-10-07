#!/usr/bin/env bash
set -euo pipefail
cd /workspace/Davigurumi
source_dir="${1:?Informe o diretório do backup.}"
restore_db="${2:?Informe o nome de um banco isolado NOVO com prefixo davigurumi_restore_.}"
/workspace/.venvs/davigurumi/bin/python - "$source_dir" "$restore_db" <<'PY'
import hashlib, json, re, sys, zipfile
from pathlib import Path
p=Path(sys.argv[1]); name=sys.argv[2]
if not re.fullmatch(r'davigurumi_restore_[a-z0-9_]{1,35}',name): raise SystemExit('Nome de banco isolado inválido.')
manifest=json.loads((p/'manifest.json').read_text())
if manifest.get('version') != 1 or hashlib.sha256((p/'database.dump').read_bytes()).hexdigest()!=manifest['database_sha256']: raise SystemExit('Backup inválido: hash ou versão incorretos.')
if 'files_archive_sha256' in manifest:
 if hashlib.sha256((p/'files.zip').read_bytes()).hexdigest()!=manifest['files_archive_sha256']: raise SystemExit('Arquivo de objetos corrompido.')
 destination=Path('.local/restored_files')/name
 if destination.exists(): raise SystemExit('O diretório isolado de arquivos já existe.')
 with zipfile.ZipFile(p/'files.zip') as archive:
  if set(archive.namelist())!=set(manifest['files']): raise SystemExit('Manifesto de arquivos incompatível.')
  for entry in archive.namelist():
   if Path(entry).is_absolute() or '..' in Path(entry).parts: raise SystemExit('Caminho inválido no backup.')
   if hashlib.sha256(archive.read(entry)).hexdigest()!=manifest['files'][entry]: raise SystemExit('Hash de imagem incompatível.')
  destination.mkdir(parents=True,mode=0o700)
  for entry in archive.namelist():
   target=destination/entry;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(entry));target.chmod(0o600)
 print('Arquivos privados restaurados em '+str(destination))
PY
docker exec davigurumi-postgres createdb -U davigurumi -T template0 "$restore_db"
docker exec -i davigurumi-postgres pg_restore -U davigurumi --exit-on-error --dbname="$restore_db" < "$source_dir/database.dump"
printf 'Restauração concluída no banco isolado %s. O banco original não foi alterado.\n' "$restore_db"

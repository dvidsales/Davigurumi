"""Run locally. Never share the master secret; share only the email-specific code."""

import argparse
import getpass
import hashlib
import hmac

parser = argparse.ArgumentParser(
    description="Gera o código de convite de um e-mail autorizado no beta."
)
parser.add_argument("email")
args = parser.parse_args()
secret = getpass.getpass("Chave DJANGO_BETA_INVITE_SECRET (entrada oculta): ")
if len(secret) < 32:
    parser.error(
        "A chave precisa ser a mesma do servidor e ter pelo menos 32 caracteres."
    )
code = hmac.new(
    secret.encode(), ("beta-v1:" + args.email.strip().lower()).encode(), hashlib.sha256
).hexdigest()
print("Código para compartilhar exclusivamente com este convidado: " + code)

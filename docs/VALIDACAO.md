# Evidências da primeira entrega

Executadas em 07/10/2026, Python 3.12.14, Django 5.2.18, Linux, SQLite.

| Verificação | Resultado |
| --- | --- |
| Instalação das versões em requirements | Concluída com TLS/verificação padrão do pip |
| `python manage.py migrate --noinput` | Migrations accounts/materials/auth/sessions aplicadas |
| `python manage.py check` | Zero problemas |
| `python manage.py makemigrations --check --dry-run` | Nenhuma alteração pendente |
| `python manage.py test` | 31 testes, 31 passaram; nenhum skip |
| Servidor Django + Chromium/Playwright | Cadastro, login automático, material/abertura 508g, preço 150, logout concluídos |
| Viewport desktop 1440 e mobile 360 | Capturas inspecionadas; quatro páginas sem overflow horizontal em 360px |
| `git diff --check` | Sem erros de whitespace |

Testes unitários/integração usam banco separado criado/destruído pelo Django.
Teste de navegador usa conta fictícia identificada e remove os dados que criou.
O teste visual inicial precisou corrigir seletores para os rótulos traduzidos do Django;
após a correção a jornada terminou com sucesso. Não era falha do fluxo de cadastro.

Cobertura executada: senha forte, e-mail case-insensitive no banco, recuperação/reset
com invalidação do token, logout POST e CSRF; isolamento na busca/detalhe/dashboard;
ownership forjado ignorado; abertura exata, nulo versus zero, rollback, reenvio
idempotente, validação de unidades/tex/precisão e constraints; escape de HTML;
paginação; fórmulas §59, taxas, ordem de descontos, arredondamento half-up, zero,
limites e valores não finitos.

Persistência do limite decimal de estoque/custo (999999,999999) conferida após
recarregar SQLite. Instruções `install_script` e `start_skill` salvas no rascunho do
ambiente; script de instalação reexecutado sem alterar dependências ou dados.
Salvar o rascunho não publica o ambiente nem a aplicação.

Correspondência parcial com PRD: T01 apenas nas rotas/tabelas atuais, T08 na calculadora
isolada, T26 apenas distinção nulo/zero. **Não** são T01/T08/T26 completos da jornada
comercial. T02–T07, T09–T25 e demais cenários integrados permanecem pendentes.

## Repetir o smoke de navegador

Opcional; Playwright/Chromium já estão disponíveis neste runtime. Com servidor na porta
8000 e Python com dependências selecionado:

```bash
DAVIGURUMI_PYTHON=/workspace/.venvs/davigurumi/bin/python node scripts/smoke_browser.cjs
```

Em outra máquina, instalar Playwright/Chromium separadamente; não são requisitos para
executar o aplicativo. O script escreve capturas em `/tmp/davigurumi-desktop.png` e
`/tmp/davigurumi-mobile.png`. Não execute esse smoke em produção.

## Limites comprováveis

Não houve validação PostgreSQL, concorrência de reservas, RLS, upload/PDF, SMTP real,
PWA/offline, restauração, exclusão LGPD, CI remoto, WCAG completa ou deploy. Não há
garantia de segurança/acessibilidade de recursos futuros. Sem dados reais nesta fase.

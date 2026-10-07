# Revisão técnica de privacidade — desenvolvimento

Não é uma política legal aprovada. Antes de convidar clientes reais, definir responsável, canal de contato, finalidades, fundamentos, prazos de retenção, termos de uso e procedimento de solicitações/incidentes com avaliação adequada.

## Controles presentes

Contas isoladas pelo proprietário; controles negativos testados para IDs/arquivos. Projeção pública por allowlist, sem notas/custos internos. Arquivos privados reencodados sem EXIF e links revogáveis/expiráveis. Cache privado desabilitado e service worker somente estático. Redação de URLs de tokens nos loggers Django, CSP e proteção CSRF. Exportação completa exige senha, não inclui credenciais e permite recuperar dados com referências/arquivos.

## Dados que exigem política

E-mail/nome da pessoa artesã, cadastro/contato do cliente, textos internos/livres, descrição e condições de orçamentos, snapshots, PDFs, fotos, declarações de aceite, eventos, sessões e backups podem conter dados pessoais. Minimize os campos e não coloque dados reais nos exemplos. Campos de texto/imagens livres também precisam entrar no procedimento de eliminação; não basta apagar um cadastro.

## Pendências que impedem abertura pública

- Não há exclusão/anonimização completa de conta, snapshots e arquivos. Proteções de imutabilidade financeira/comercial exigem tratamento deliberado conforme retenção definida; não prometer que dados pessoais serão preservados para sempre.
- Não há tombstones de exclusão aplicados na restauração nem ciclo de expurgo de backups. Um backup antigo pode reintroduzir dados que deveriam ter sido eliminados.
- Ausência de política publicada, canal de privacidade/resposta a incidentes e verificação de acesso operacional por fornecedor.
- Logs do proxy/host, backups independentes, TLS, permissões do armazenamento e segredo de produção precisam ser configurados/verificados no ambiente escolhido.
- Exportação/importação mantém histórico pessoal; pacote contém informações sensíveis e precisa de armazenamento/controlos de acesso adequados. A assinatura valida autenticidade na mesma chave, não criptografa o conteúdo.

A revogação de link impede novos acessos, mas não recolhe PDFs/imagens já baixados. Aceite por link não verifica identidade do destinatário. Limite de tentativas por IP usa endereço direto; proxy confiável e tratamento de endereço compartilhado precisam ser definidos na hospedagem.

## Procedimento inicial de incidente

Suspender novos acessos ao ambiente afetado, preservar evidências mínimas em armazenamento restrito, rotacionar segredo/tokens e revisar impacto em sessões, e-mail e arquivos. Restaurar apenas em base isolada e reconciliar estoque/financeiro; não colocar a restauração em serviço antes de reaplicar eventuais exclusões/tombstones. Responsáveis, comunicação e prazos legais ainda precisam de definição.

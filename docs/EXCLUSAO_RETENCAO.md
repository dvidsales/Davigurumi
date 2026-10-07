# Exclusão e retenção: procedimento técnico

A exclusão é **administrativa**, irreversível e não fica exposta como rota HTTP. Os comandos simulam por padrão. Não executar `--apply` em dados reais apenas para experimentar. Os testes automatizados usaram bancos e arquivos sintéticos.

O procedimento técnico está implementado; isso não cria uma política legal. Antes de operação pública, o responsável deve aprovar finalidades, prazos por categoria, tratamento de obrigações legais, canal de solicitações e responsáveis por incidentes. Se houver obrigação de retenção, manter a conta suspensa e aguardar o prazo aplicável; não apagar histórico financeiro/comercial sem essa avaliação. Este comando elimina a conta inteira; anonimização seletiva com retenção parcial é uma evolução separada.

## Preparar o registro externo

Configurar `DJANGO_PRIVACY_LEDGER_DIR` explicitamente, em diretório privado **independente do banco, dos arquivos e das cópias que serão restauradas**. Configurar `DJANGO_PRIVACY_LEDGER_KEY` com segredo próprio, diferente da chave Django. Criar o diretório com acesso restrito; em produção, montar somente para leitura no processo web e dar escrita apenas ao procedimento administrativo. Manter cópia independente desse registro e segredo.

Não imprimir/versionar a chave e não armazená-la no pacote exportado. Não trocar a chave sem migrar/verificar todos os registros existentes. Sem registro/chave em produção, sessão e portal ficam bloqueados; assinatura inválida também bloqueia a conta. Restaurar o registro externo junto de um banco antigo desfaz essa defesa, portanto ele nunca deve ser substituído pela versão antiga do backup.

## Executar uma solicitação

1. Verificar a identidade e o escopo da solicitação por canal administrativo; registrar UUID do procedimento e identificador da política aprovada, sem colocar nome, e-mail ou relato pessoal no registro técnico.
2. Exportar somente se solicitado e autorizado; o pacote é sensível e deve ter destino/retencão próprios. Suspender a conta com senha pela tela de segurança e revogar links.
3. Pausar tráfego e tarefas; conferir cópia restaurável e necessidade de retenção antes da exclusão. Usar credenciais **de manutenção**: o usuário restrito da aplicação não precisa ter privilégios para alterar triggers.
4. Obter prévia:

```bash
python manage.py erase_account UUID_DA_CONTA \
  --case UUID_DO_PROCEDIMENTO --policy IDENTIFICADOR_DA_POLITICA
```

5. Depois da revisão administrativa, o mesmo comando com `--apply` executa a exclusão. Requer conta suspensa e registro externo configurado. Nunca executar como um passo automático da interface.

O comando bloqueia a conta por tombstone assinado e persistido **antes** de apagar dados. Exclui conta/demo, relações de estoque, fichas, snapshots, PDFs binários, dinheiro, textos, eventos, prévias, sessões e arquivos privados. Inclui uploads órfãos identificados na pasta da conta, preservando arquivos referenciados por outra conta. Opera com armazenamento local privado; outro backend exige adaptação e teste específico.

PostgreSQL: a manutenção toma locks exclusivos e suspende apenas quatro guardas de imutabilidade, restaurando-os na mesma transação. Não desativa constraints/FKs nem triggers de outras tabelas. Falhas revertem alterações no banco e a suspensão dos guardas; o tombstone externo permanece para impedir reativação. Arquivos são removidos após commit. Se houver falha de armazenamento, repetir a reaplicação para remover os remanescentes. Não apagar tombstones para contornar um erro.

## Restaurar sem reintroduzir exclusões

Restaurar banco/arquivos em destino **isolado**, sem tráfego nem tarefas de envio. Conectar ao registro externo atual e conferir a prévia:

```bash
python manage.py reapply_erasure
```

Após revisar o destino, executar `reapply_erasure --apply`, reconciliar estoque e verificar arquivo/logs/cotas. O comando valida todas as assinaturas antes de tocar nas contas restauradas e reaplica exclusões, inclusive de arquivos remanescentes. Sessão/portal também consultam tombstones, e a importação de pacote recusa origem/destino excluídos. Mensagens pendentes de conta excluída/suspensa ou sem consentimento não são enviadas.

Esses bloqueios protegem a aplicação, não impedem alguém com credenciais diretas de banco de ler um backup. Cópias baixadas ou entregues a terceiros não podem ser recolhidas automaticamente.

## Expirar cópias locais

`scripts/prune_backups.py` reconhece somente diretórios com `database.dump`, `files.zip` e `manifest.json`, respeita a data do manifesto e simula por padrão. Não percorre pastas desconhecidas, links simbólicos ou pastas com arquivos adicionais.

```bash
python scripts/prune_backups.py RAIZ_DAS_COPIAS --retention-days PRAZO_APROVADO
```

O mesmo comando com `--apply` elimina as cópias reconhecidas já vencidas. O prazo é informado pelo responsável; não foi inventado nem aplicado a backups existentes neste trabalho. **Nunca colocar o registro de exclusões nessa raiz.** Provedores externos, versionamento de objetos, snapshots, logs e cópias independentes precisam de expurgo/agendamento conforme a política do ambiente. O helper local não controla esses serviços.

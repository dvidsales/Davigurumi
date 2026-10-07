# Registro de decisões — 07/10/2026

| ID | Escolha | Origem e estado |
| --- | --- | --- |
| D01 | Python/Django + templates | Preferência por Python do usuário; escolha técnica para manutenção simples |
| D02 | Continuar desenvolvimento sem aguardar teste manual | Autorização explícita mais recente do usuário |
| D03 | PostgreSQL 17 para concorrência; SQLite opcional local | PostgreSQL e SQLite validados; bases distintas, sem transferir cadastros silenciosamente |
| D04 | Média disponível para estimar, FIFO para alocar, custo da camada para realizar | Implementado conforme referência; permitir futura seleção por ficha |
| D05 | Consumo explícito; timer não baixa estoque | Implementado e testado |
| D06 | Versões/PDF congelados; aditivo com novo aceite | Implementado; casos que exigem conciliação são rejeitados |
| D07 | Uma sessão ativa por pessoa | Implementado com constraint; confirmar múltiplos trabalhos em paralelo numa evolução |
| D08 | Decimal/half-up e fórmulas §59 | Implementado; subtotais reais não são lucro final sem despesas completas |
| D09 | SMTP configurável, console padrão | Outbox/retentativa validadas; provedor real ausente |
| D10 | Fotos privadas, EXIF removido, publicação explícita | Implementado; armazenamento atual é local ignorado |
| D11 | Referrer-Policy same-origin no portal | Chromium HTTP enviou Origin null com no-referrer; same-origin preserva CSRF nativo e impede referrer externo com token |
| D12 | Demo com proprietário separado | Implementado; cópia não leva estoque, custos ou finanças fictícias |
| D13 | Pacote completo assinado, destino vazio | Round-trip validado; não mescla IDs; aceita chave original, revoga links e invalida aceite importado para novos pedidos |
| D14 | Backup local para prova de recuperação | Restaurado; falta destino independente, agendador e retenção |
| D15 | `main` revisada + branches de funcionalidade | Recomendação técnica; `develop` opcional quando houver integração paralela; nenhum merge/proteção criado |
| D16 | Verde profundo/sálvia provisórios | Identidade final não foi aprovada |
| D17 | Sem serviços pagos/deploy/dados reais | Dentro da autorização atual; preparar proposta concreta antes de operação externa |

Padrões de desenvolvimento: validade 15 dias (editável), fuso America/Sao_Paulo, arquivos até 5 MB/16 milhões de pixels, 100 imagens por conta/10 por versão e imports até 2000 linhas. São limites do protótipo, não cotas contratadas em fornecedor.

Retenção legal, exclusão, tombstones, push e infraestrutura permanecem pendentes. Essas pendências devem ser apresentadas separadamente do que já funciona, sem afirmar produção pronta ou cumprimento integral do PRD.

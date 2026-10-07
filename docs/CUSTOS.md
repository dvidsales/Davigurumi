# Custos e cotas

## Comprovado nesta entrega

Desenvolvimento usa runtime existente, Django/Python locais e SQLite. Nenhum serviço
pago, cartão, domínio, gateway ou pay-as-you-go foi ativado. Não há custo adicional de
provedor do produto contratado nesta tarefa. Isso não significa hospedagem pública
gratuita ou disponibilidade garantida.

## Fontes a reconferir na implantação

O PDF cita valores em 07/10/2026; **não foram reconferidos online nesta entrega**.
Não usar esses valores como orçamento confirmado. As versões dos pacotes instalados
estão travadas em `requirements.txt`.

| Serviço / fonte oficial | Aplicação possível | Pendência e alternativa |
| --- | --- | --- |
| [Render Free](https://render.com/docs/free) | Processo Python/Django | Validar pausa, armazenamento efêmero, elegibilidade e banco; alternativa máquina existente |
| [Neon pricing](https://neon.com/pricing) | PostgreSQL gerenciado | Confirmar armazenamento/compute/conexões, região e limite sem cobrança; alternativa PostgreSQL local no desenvolvimento |
| [Supabase pricing](https://supabase.com/pricing) | PostgreSQL/storage do desenho original | PDF cita 500MB banco/1GB storage; não confirmado aqui; auth Django evita dependência de Supabase Auth |
| [Supabase SMTP](https://supabase.com/docs/guides/auth/auth-smtp) | Auth da alternativa React | SMTP padrão não assumido como produção; alternativa provedor transacional validado |
| [Brevo pricing](https://www.brevo.com/pricing/) | SMTP transacional | Validar cota gratuita, domínio/remetente e termos; nenhum binding configurado |
| [Supabase backups](https://supabase.com/docs/guides/platform/backups) | Cópias do banco | Não assumir cópia de objetos; destino independente ainda pendente |
| [Cloudflare R2](https://developers.cloudflare.com/r2/pricing/) | Objetos privados | Excedentes/cadastro/possível cobrança precisam ser avaliados; não ativado |
| [Vercel Hobby](https://vercel.com/docs/plans/hobby) | Alternativa frontend | Verificar restrição comercial; não escolhido para Django |

Hipótese de piloto do PRD: cinco usuárias, mil materiais, mil orçamentos e mil imagens
de 300KB ≈ 300MB antes de variantes/backups. É hipótese, não consumo medido.
Proposta de alerta a 70% das cotas e bloqueio de novos uploads ao atingir limite,
preservando leitura/exportação quando possível. Não apagar histórico para liberar cota.

Responsável e orçamento público ainda não definidos. R$ 0 é objetivo do PRD, não
promessa: Python público, e-mail e backup podem exigir revisão concreta do arranjo.

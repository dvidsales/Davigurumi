# Testar em computador, celular e tablet

Faça os testes **no navegador do computador e no celular real**. Use tablet também se pretende trabalhar nele. Não é necessário comprar dispositivos: comece pelos que você já possui e registre os modelos/navegadores. Trocar o tamanho da janela ou usar a simulação do navegador não substitui um aparelho real.

Use somente contas, clientes, fotos e valores fictícios. O ambiente de teste deve continuar privado, com login, cadastro fechado quando apropriado e cópia dos dados antes de mudanças. O aceite por link deve ser feito com um orçamento de teste; esse link dá acesso a quem o possuir.

## Onde abrir

Abra o **mesmo endereço privado de teste** no computador e no celular/tablet. `localhost` e `127.0.0.1` no celular apontam para o próprio celular, não para o computador ou para este cloud. Não abra uma porta pública ou desative HTTPS para testar. Quando houver uma prévia privada ou ambiente de homologação protegido, use sua URL nos aparelhos; para PWA/instalação é necessário HTTPS, salvo localhost no próprio computador.

O servidor atual é de desenvolvimento e está ligado apenas ao loopback do cloud. Este trabalho não configura hospedagem pública ou um endereço externo para o celular. Não colocar banco SQLite, arquivos privados ou backups numa pasta pública para viabilizar acesso.

## Matriz mínima

| Aparelho | Navegador | Prioridade | Verificar |
| --- | --- | --- | --- |
| Seu computador | Chrome ou Edge atualizado | Obrigatório | Jornada completa, teclado, importações e PDFs/XLSX |
| Computador, se disponível | Firefox; Safari no Mac | Recomendado | Formulários, downloads e diferenças de navegação |
| Seu celular Android | Chrome atualizado | Obrigatório se for seu celular | Toque, teclado, arquivos, timer e instalação |
| Seu iPhone | Safari atualizado | Obrigatório se for seu celular | Fotos, arquivos, timer e adicionar à Tela de Início |
| Tablet Android ou iPad | Chrome ou Safari correspondente | Obrigatório se você pretende usá-lo | Orientação, tabelas, teclado e formulários |

Não precisa executar todos os navegadores de todos os sistemas. Se pretende atender usuários Android e iPhone, é recomendável testar ambos antes de disponibilizar para eles.

## Roteiro de 30–45 minutos

1. **Conta:** entrar/sair, senha errada, recuperar e trocar senha quando SMTP de teste estiver configurado. Confirmar que a outra sessão precisa entrar novamente após troca. Não executar exclusão real para testar a interface.
2. **Materiais:** criar fio com 508 g a R$0,10/g, preencher características, abrir detalhes, editar, arquivar/reativar. Verificar teclado numérico e separador decimal. Arquivar não muda estoque.
3. **Ficha e orçamento:** ficha com 120 g e 1 h a R$30; orçamento de uma unidade R$63. Publicar com imagem fictícia. Abrir o link em janela privada ou outro aparelho, conferir ausência de custos/notas internas e aceitar.
4. **Pedido:** registrar sinal R$20 e criar pedido: saldo R$43. Reservar, iniciar timer, bloquear a tela/alternar app por alguns minutos, voltar e pausar. O timer deve manter o tempo; navegação não cria uma segunda sessão.
5. **Estoque e custo:** consumir 50 g: físico 458. Recuperar sobra física de 10 g: físico 468; custo consumido líquido R$4. Registrar despesa R$5 e revertê-la: histórico permanece e despesa líquida volta a zero.
6. **Entrega e dinheiro:** registrar produção, entrega e recebimento R$43. Confirmar concluído/entregue/quitado, recebido líquido R$63 e saldo zero. Não há integração bancária real.
7. **Arquivos:** escolher foto pela galeria e, se disponível, pela opção do sistema de tirar foto; baixar PDF e XLSX e abrir no aparelho. No celular, conferir onde os arquivos foram salvos e o botão compartilhar do sistema.
8. **Importação:** baixar modelo, remover o exemplo, importar duas linhas fictícias, conferir prévia antes de confirmar e repetir confirmação sem duplicar estoque. Nunca usar arquivo pessoal nesta etapa.
9. **Conexão e instalação:** instalar/adicionar à Tela de Início, abrir por esse atalho, desconectar internet e conferir aviso/operacões bloqueadas. O app não grava estoque, aceite ou pagamentos offline. Reconectar e confirmar que botões originalmente desativados continuam assim.
10. **Isolamento:** entrar com outra conta e tentar URLs privadas da primeira; deve negar acesso. Sair e usar Voltar: conteúdo privado não deve ficar disponível para novas consultas. PDF já baixado permanece no aparelho.

## Tela e acessibilidade

No computador, navegar com Tab/Shift+Tab, Enter e Espaço; conferir foco visível, link “Pular para o conteúdo” e tabelas roláveis pelo teclado. Ampliar o navegador a 200% e verificar leitura/preenchimento. No celular/tablet, repetir em retrato e paisagem e com tamanho de texto maior; conferir que o teclado não impede salvar ou ler erros. Tabelas podem rolar dentro da própria área, sem empurrar toda a página horizontalmente.

Se possível, ativar VoiceOver (iPhone/iPad/Mac), TalkBack (Android) ou NVDA (Windows). Conferir títulos, nomes dos campos, erros e botões. Uma análise automática sem erros não certifica acessibilidade para leitor de tela.

## Como registrar feedback

Copiar este modelo para cada problema:

```text
Aparelho / versão do sistema:
Navegador / versão / instalado ou aba:
Página e passos para reproduzir:
Esperado:
Aconteceu:
Orientação / conexão:
```

Usar capturas com dados fictícios. Não enviar senhas, links completos de aceite, tokens de recuperação, pacotes completos ou dados pessoais. Se houver perda/duplicação de estoque ou dinheiro, interromper o teste naquele pedido e registrar os passos antes de tentar corrigir.

## O que já foi verificado aqui

Chromium com jornada completa, 31 telas a 360 px e telas principais a 768/1024 px; isolamento, arquivos, cache somente estático e aviso offline. A análise WCAG automática é opcional no script `scripts/smoke_browser.cjs` via `DAVIGURUMI_AXE_PATH`; o script exige base descartável. Evidências e limites em [VALIDACAO](VALIDACAO.md).

# Interface mobile first

A interface parte do celular e amplia o layout em telas maiores. A mudança é de apresentação e navegação: contas, permissões, estoque, cálculos, aprovações, pagamentos e histórico continuam nos mesmos serviços e URLs.

## Navegação

O menu anterior tinha 13 entradas no mesmo nível. Agora tem cinco áreas:

| Área | Conteúdo |
| --- | --- |
| Início | Visão geral do ateliê |
| Vendas e produção | Orçamentos, clientes, pedidos, calendário e biblioteca de peças |
| Estoque | Materiais, compras/fornecedores, histórico e reposição |
| Financeiro | Recebimentos/caixa e relatórios |
| Mais | Calculadora, notificações, importar/exportar, demonstração e segurança da conta |

No celular e tablet há cabeçalho compacto, atalhos inferiores para Início/Vendas/Estoque/Caixa/Menu e um menu em diálogo nativo. O grupo da página atual vem aberto; os outros podem ser expandidos. O menu tem rolagem própria, mantém o foco dentro dele, fecha por Escape, botão ou toque fora e devolve o foco ao controle que o abriu. Abrir/fechar o menu preserva os campos já preenchidos.

A partir de 1100 px, a navegação vira uma barra lateral com os mesmos grupos. Sem JavaScript, uma navegação alternativa usa elementos `details` nativos. Não é necessário instalar um aplicativo no celular.

## Layout e acessibilidade

- Controles principais e de navegação com área de toque de pelo menos 48 px; campos com texto de pelo menos 16 px, evitando o zoom automático comum em formulários no iOS.
- Zoom do navegador permitido; texto ampliado a 200% conferido em largura de 320 px. Conteúdo e palavras longas podem se reorganizar, sem impor largura fixa à página.
- Respeito às áreas seguras do aparelho, espaço reservado à barra inferior e medidas dinâmicas para limitar a altura do menu em orientação paisagem.
- Formulários em uma coluna no celular, labels explícitos e botões de ação empilhados. Em janelas baixas com campo em foco, a barra inferior cede espaço.
- Busca de materiais visível e filtros secundários expansíveis dentro da página, sem painel flutuante.
- Listas tabulares simples viram cartões abaixo de 600 px, preservando cabeçalhos e papéis acessíveis. Tabelas complexas mantêm rolagem na seção. Sem JavaScript, permanecem tabelas roláveis.
- Foco visível, atalho para o conteúdo, estados atuais da navegação, contraste e nomes acessíveis dos ícones. Movimento respeita `prefers-reduced-motion`.
- No celular, o formulário de login aparece antes do texto de apresentação.

Critérios usados como referência: [WCAG 2.2 — Reflow, 1.4.10](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html), [Resize Text, 1.4.4](https://www.w3.org/WAI/WCAG22/Understanding/resize-text.html), [Target Size Minimum, 2.5.8](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html), [Focus Not Obscured, 2.4.11](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html) e navegação por teclado/ausência de bloqueio do foco. O alvo de 48 px adotado nos controles principais é maior que o mínimo de 24 px do critério 2.5.8; links no meio de textos têm exceções próprias na norma. Os documentos de reflow, foco e tamanho de alvo foram consultados no repositório oficial W3C/WCAG, pois o acesso direto ao site foi bloqueado.

A implementação usa recursos web nativos, não adiciona framework JavaScript ou dependência de produção. Não se declara conformidade integral com todas as WCAG apenas por passar ferramentas automáticas.

## Validação

- 186 testes aprovados no PostgreSQL; SQLite: 181 aprovados e 5 exclusivos do PostgreSQL ignorados.
- Jornada completa no Chromium: criação, aprovação, sinal, pedido, consumo, produção, entrega, quitação, compras, importação/exportação, isolamento e demonstração. 31 telas a 360 px, verificações adicionais em 768/1024 px, sem erros JS/5xx, overflow ou violações detectadas pelo axe no conjunto configurado.
- Roteiro mobile: 12 páginas em 320, 360, 390, 430, 600, 768, 1024 e 1440 px — 96 verificações de layout. Menu por teclado, Escape, toque fora, rolagem, preservação de formulário, mudança de tamanho, orientação paisagem, movimento reduzido e fallback sem JavaScript.
- Texto ampliado a 200% em 320 px; menu, cartões, desktop e login verificados pelo axe com critérios WCAG 2/2.1/2.2 AA disponíveis na ferramenta.

As verificações usam dados sintéticos em banco isolado. Não foram feitas alterações nas contas do ambiente hospedado. O download do WebKit foi bloqueado pela rede (HTTP 403), portanto **Safari/WebKit e dispositivos reais não foram executados nesta revisão**. É necessário conferir no iPhone/Android: teclado, rotação, barras do navegador, VoiceOver/TalkBack, seleção de arquivos, tabelas e formulários longos.

## Capturas

- [Novo material no celular](images/mobile-novo-material.png)
- [Menu no celular](images/mobile-menu.png)
- [Lista de materiais no celular](images/mobile-materiais.png)
- [Materiais no computador](images/mobile-desktop.png)

## Reproduzir os testes de navegador

Com Playwright/Chromium disponíveis, serviço apontando para **banco descartável** e dependências do projeto instaladas:

```bash
DAVIGURUMI_SMOKE_ISOLATED=1 DAVIGURUMI_SMOKE_URL=http://127.0.0.1:8111 DAVIGURUMI_AXE_PATH=/caminho/axe.min.js node scripts/smoke_mobile.cjs
```

O roteiro cria uma conta e um material fictícios. Nunca aponte para banco/serviço com dados reais. `DAVIGURUMI_AXE_PATH` é opcional, mas sem ele a auditoria axe não roda; o relatório mostra quantas verificações de acessibilidade foram executadas. Saídas ficam em `/tmp/davigurumi-mobile-review`, ou no diretório informado por `DAVIGURUMI_MOBILE_OUTPUT`. `scripts/smoke_browser.cjs` mantém a verificação da jornada completa. O GitHub Actions também executa o roteiro mobile no PostgreSQL isolado do job, usando Chrome e ferramentas de desenvolvimento fixadas (Playwright 1.62.1 e axe-core 4.11.0), e publica capturas sintéticas no artefato `mobile-review`.

## Ver no ambiente de testes

Depois de integrar o PR, no serviço Render selecione **Manual Deploy → Deploy latest commit**. O build gera novos nomes de CSS/JS no manifesto. Não é necessário editar variáveis, recriar banco, gerar novos convites ou sincronizar o Blueprint para esta mudança. Se o celular ainda mostrar a tela anterior, recarregue a página; a atualização não força recarregamento de formulários abertos.

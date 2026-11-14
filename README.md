# CrossPlatform App Converter

**Versão:** 0.15.0 experimental · **Distribuição:** instalador para Windows x64 · **Dependências:** Python 3.11+ para rodar do código-fonte; o aplicativo instalado inclui JADX portátil e JRE para recuperação de APK.

> **Aviso:** este projeto não é milagroso. A análise e os projetos-base podem conter erros ou bugs, omitir partes do aplicativo e até resultar em um app que não funciona. APKs/IPAs arbitrários não são convertidos automaticamente em aplicativos funcionais equivalentes. Revise, compile e teste toda saída na plataforma de destino antes de publicar ou distribuir.

Ferramenta de análise estática para pacotes APK e IPA, com uma estimativa estrutural de compatibilidade e apoio experimental à reconstrução. O instalador configura o próprio conversor em `Program Files`; ele não transforma os aplicativos analisados em APK ou IPA. As tentativas de reconstrução continuam gerando ZIPs experimentais com projeto-base, evidências, tarefas e recursos candidatos. **O código e a interface do app de origem não são convertidos em um aplicativo funcional.**

## Licença

Este repositório ainda não inclui uma licença para o projeto. Os avisos e as licenças dos componentes de terceiros estão descritos em `THIRD_PARTY_NOTICES.md`.

O Windows pode exibir uma solicitação de administrador para instalar em `Program Files`. O assistente mostra o aviso de limitações, o destino e uma lista dos arquivos e pastas antes de instalar, além dos nomes durante o progresso. Ele cria um atalho no menu Iniciar e uma opção de desinstalação do Windows. O instalador ainda não tem assinatura digital; o Windows pode mostrar um aviso de editor desconhecido.

## Iniciar

- Para instalar no Windows, execute `CrossPlatformAppConverter-0.15.0-Windows-Setup.exe` e siga o assistente. Para remover, use Aplicativos instalados / Adicionar ou remover programas do Windows.
- A interface detecta português do Windows e, nos demais idiomas, usa inglês. O instalador oferece português brasileiro e inglês. A interface acompanha o tema claro/escuro definido no Windows e percebe mudanças enquanto está aberta.
- Para publicar no GitHub, anexe o instalador `.exe` a uma Release e mantenha também o código-fonte e instruções de compilação no repositório. Não inclua APKs/IPAs de amostra nem a pasta local `work/`.

- Interface: execute `run_gui.py` com Python 3.11.
- Linha de comando: `python run_cli.py caminho\app.apk caminho\app.ipa --reports .\reports`.
- Plano de reconstrução e rascunho: `python run_cli.py caminho\app.apk --attempt-conversion --attempt-dir .\attempts`.
- Recuperação de código APK aproximado: `python run_cli.py caminho\app.apk --recover-apk --recover-dir .\recovered`.
- A recuperação também gera `swiftui-layout-preview.swift`, um catálogo navegável no projeto-base Xcode, `android-layout-source-map.json` com referências estáticas `R.layout` e um mapa das imagens Android recuperadas que foram copiadas ao catálogo iOS.
- Testes: `python -m unittest discover -s tests -v`.

Se fornecer apenas um pacote, o programa analisa sua estrutura. Se fornecer um APK e um IPA, também compara indícios de funcionalidades. Os pacotes são lidos diretamente e não são extraídos.

## Arquitetura

```text
run_gui.py / run_cli.py
          │
       cpc.analyze ─────── cpc.reports
          │
   ┌──────┴──────┐
analyzers       compatibility
  ├─ android.py  └─ comparação por evidências
  └─ ios.py
          │
    portability.py ── projeto-base + recursos nativos + plano
    recovery.py ───── JADX portátil: Java aproximado e recursos Android
```

- `cpc/analyzers/android.py`: identifica manifesto XML textual ou Android AXML binário, permissões, SDK, componentes, bibliotecas nativas e marcadores de frameworks.
- `cpc/analyzers/ios.py`: lê `Info.plist`, frameworks, extensões, descrições de privacidade e metadados do IPA.
- `cpc/compatibility.py`: compara evidências de recursos entre um APK e um IPA.
- `cpc/reports.py`: resumo de tela e relatórios HTML/JSON com nome exclusivo.
- `cpc/portability.py`: gera projeto-base, inventário estruturado de evidências e lista de reconstrução; o ZIP também inclui recursos candidatos limitados e nunca altera o pacote original.
- `cpc/recovery.py`: chama o JADX portátil, incluído na distribuição, somente para APK; guarda Java aproximado, recursos decodificados, inventário de layouts/menus/strings e referência SwiftUI visual experimental, em pasta nova, sem instalar nem executar o pacote analisado.
- `run_gui.py`: interface Tkinter; `run_cli.py`: linha de comando.
- `tests/`: testes com pacotes sintéticos, sem apps reais.

## Estado das funcionalidades

| Estado | O que existe |
|---|---|
| Implementado | Detecção de APK/IPA; leitura do manifesto Android compilado ou textual; leitura de `Info.plist`; inventário do ZIP; sinais de permissões, componentes, bibliotecas e frameworks; comparação Android/iOS; relatórios HTML/JSON; interface gráfica e CLI; testes sintéticos. |
| Experimental | Pontuação de dificuldade por heurística; geração de esqueleto Android/SwiftUI; plano JSON/Markdown; importação de imagens compatíveis para recursos nativos; tentativa de recuperar Java/recursos de APK pelo JADX 1.5.6; projeto-base Xcode com catálogo navegável de até 100 layouts XML, mapa de referências `R.layout` em Java e imagens raster selecionadas em `Assets.xcassets`, sem associação automática a telas. A prévia usa placeholders para widgets dinâmicos, não contém ações/lógica e não foi compilada. O decompilador pode reportar erros e produzir código incompleto. Não converte Java para Swift. |
| Planejado | Mais regras de compatibilidade; fingerprinting de dependências; importação opcional de relatórios do JADX/apktool; extração seletiva de recursos para uma nova pasta; testes dinâmicos em emuladores; validação de comportamento equivalente. |

## Limitações e segurança

- APK/IPA contém código compilado, não o projeto-fonte original. A recuperação Java é parcial, Android-only e propensa a erros; não recupera fielmente Kotlin, nomes, comentários, estrutura de projeto ou código nativo.
- O JADX bundled não executa nem instala o APK, mas processa o conteúdo como entrada. Caminhos inseguros, não canônicos ou que colidem no Windows são omitidos antes do processamento e listados no relatório. A recuperação pode usar até 2 GB de memória e demora vários minutos; a saída é gravada em uma pasta nova e inclui erros e contagens.
- O ZIP de tentativa é apenas material inicial para reconstrução. Recursos são selecionados por extensão/nome, não são convertidos nem validados, e podem não ser úteis. O ZIP não é instalável como APK/IPA e não garante funcionamento.
- A referência SwiftUI representa somente alguns controles XML em uma prévia; pode não compilar em todo projeto e não reflete temas, medidas, navegação, estado, interação ou telas criadas em runtime. Consulte `swiftui-preview-report.json` e revise cada componente.
- `android-layout-source-map.json` é uma busca textual no Java aproximado. Uma referência `R.layout` pode vir de adapter, diálogo ou código não executado; o mapa não infere tela inicial nem fluxo de navegação.
- `native-resource-map.json` lista imagens decodificadas copiadas para revisão e `Assets.xcassets`. Nomes/densidades não são interpretados semanticamente; nenhuma imagem é ligada automaticamente a uma view nem validada visualmente.
- O manifesto Android em XML textual com DTD/entidades é rejeitado; a cópia de candidatos filtra caminhos perigosos e arquivos muito grandes, mas ainda não equivale a uma auditoria completa de formatos compactados.
- O inventário de nomes não identifica necessariamente a função de cada recurso ou biblioteca. Ausência de um marcador não prova que uma funcionalidade não existe.
- A pontuação é uma heurística, não prazo, custo, auditoria de segurança nem garantia de compatibilidade.
- O analisador não executa os pacotes, não verifica comportamento visual, licenças, assinatura, integridade ou vulnerabilidades.
- Bibliotecas `.so` do Android e binários Mach-O do iOS não podem ser reutilizados diretamente entre plataformas.
- O esqueleto Android exige JDK e Android SDK para compilar. O esqueleto iOS exige macOS e Xcode. Esta máquina Windows não consegue assinar ou compilar o app iOS.
- IPA pode conter perfil de provisionamento assinado; a versão atual apenas o inventaria e não decodifica a assinatura CMS ou os entitlements.
- Os relatórios podem conter caminhos locais e metadados do aplicativo. Guarde-os em local apropriado.

## Preservação de arquivos

A análise não extrai nem modifica o APK/IPA selecionado. Relatórios e esqueletos são gravados em arquivos ou diretórios novos; se o nome já existir, um sufixo numérico é acrescentado. Nenhum arquivo de origem é sobrescrito.

Consulte [VALIDATION.md](VALIDATION.md) para os pacotes públicos usados na validação, hashes e resultados. Os downloads de teste não acompanham o programa.

## Gerar o instalador Windows

`build_windows.ps1` cria um ambiente virtual local em `work/build-env`, instala nele o PyInstaller e baixa o JADX 1.5.6 portátil (cerca de 99 MB, com runtime Java incluído). O script confere o SHA-256 oficial antes de extrair e distribuir o JADX junto ao executável. A distribuição resultante é maior; o computador de destino não precisa instalar Python, Java nem JADX.

Execute `powershell -ExecutionPolicy Bypass -File .\build_installer.ps1`. O script compila o aplicativo e gera um instalador único com NSIS 3.13, baixado para `work/` e conferido por SHA-256 antes do uso. O instalador final fica em `work/installer-release/`. A compilação requer internet na primeira execução para obter PyInstaller, JADX e NSIS; a instalação pelo usuário requer permissão de administrador por usar `Program Files`.

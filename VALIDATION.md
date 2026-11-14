# Validação com pacotes publicados pelos projetos

Aviso: resultados experimentais podem conter erros/bugs, omitir componentes ou não funcionar. A integridade do ZIP e a compilação de um esqueleto não demonstram equivalência funcional com o app de origem.

Os pacotes abaixo foram baixados somente para análise estática local. Eles não foram instalados, abertos nem executados e não são incluídos no pacote de distribuição. Os arquivos de validação estão sob `work/samples/`, ignorado pelo Git e pelo empacotamento do aplicativo.

## APK: cliente F-Droid

- Fonte oficial do projeto/repositório: [página do F-Droid](https://f-droid.org/en/packages/org.fdroid.fdroid/).
- Arquivo: `org.fdroid.fdroid_2000053.apk` (12.774.751 bytes).
- SHA-256: `DAC55A0D17B1EDF7E7286B48CFBD70C7C52FBB32A00AF062C68830A437C47959`.
- Resultado: pacote identificado como `org.fdroid.fdroid`, versão `2.0.3`, manifesto AXML lido, 973 entradas listadas e quatro arquivos de biblioteca agrupados como uma dependência com quatro variantes ABI.
- Tentativa: ZIP de projeto iOS com 490 recursos candidatos; dez caminhos que colidiam após normalização foram relatados e ignorados. O ZIP não é IPA instalável.

## APK: NewPipe

- Fonte oficial: [página do F-Droid](https://f-droid.org/en/packages/org.schabi.newpipe/), que identifica Team NewPipe como desenvolvedor e publica o APK correspondente ao código-fonte do projeto.
- Arquivo: `org.schabi.newpipe_1015_cb84069.apk` (11.507.122 bytes).
- SHA-256 local: `18447BFB1E06D113EDC88DF93F471827280DE06F6F3D4DC42F56F28B9C1BAB79`.
- Resultado: identificado como `org.schabi.newpipe`, versão `0.29.1`, 1.375 entradas listadas.
- Tentativa APK → iOS: ZIP com 478 recursos candidatos e 22 caminhos colidentes ignorados.

## IPA: cliente Sheaf (desenvolvimento, sem assinatura)

- Fonte oficial: [repositório iOS do Sheaf](https://github.com/sheaf-project/ios) e [release oficial de desenvolvimento](https://github.com/sheaf-project/ios/releases/tag/dev).
- Arquivo: `Sheaf-unsigned-20261027-221436-494f3a4.ipa` (17.908.969 bytes).
- SHA-256: `A8B76580C77473F8A68116E1BA6B335F8E6C2F663B545051D62CB3D03BA384B7`.
- Resultado: bundle principal identificado como `systems.lupine.sheaf`, versão `1.7`, iOS mínimo `17.6`; o executável principal `Payload/Sheaf.app/Sheaf` foi reconhecido e o app Watch aninhado foi tratado como metadado separado.
- Tentativa: ZIP de projeto Android com sete recursos candidatos. O ZIP não é APK instalável.

## APK e IPA correspondentes: Hiddify 5.5.5

- Fonte oficial: [releases do Hiddify](https://github.com/hiddify/hiddify-app/releases/tag/v5.5.5); ambos são artefatos da mesma versão publicada pelo projeto.
- APK `Hiddify-Android-arm64.apk` (63.989.614 bytes), SHA-256 `D607FCBBB3566BC79DD8070979E74E5AFED25F59C0643DA950AAE430A4260C0D`.
- IPA `Hiddify-iOS.ipa` (104.704.837 bytes), SHA-256 `55C3712AD89FAE1B9BA0421E06B19A6404F896D52BA4A2C9FD16C294216294D0`.
- Os hashes conferem com os publicados nos metadados da release. A análise leu versões `5.5.5` nos dois lados e reconheceu o runtime Flutter em ambas; também apontou diferenças de recursos, permissões e bibliotecas nativas.
- Tentativa APK → iOS: ZIP com 497 recursos candidatos; três colisões de nomes foram listadas.
- Tentativa IPA → Android: ZIP com 396 recursos candidatos; nenhum item foi ignorado.
- A tentativa pela GUI também foi exercitada: gerou outro ZIP com 495 recursos e cinco itens relatados (dois caminhos longos para o destino escolhido e três colisões). O destino e o sistema de arquivos podem alterar quais recursos cabem no limite de caminho.
- O comparador ainda mostra uma dificuldade heurística alta. Isso não mede equivalência ou qualidade de conversão; cada plataforma possui código nativo e recursos próprios.

## Limite da validação

Esses casos verificam leitura de pacotes e geração do material inicial. Eles não provam equivalência funcional. O Hiddify é um par da mesma versão; F-Droid e NewPipe são amostras apenas Android, e Sheaf é uma amostra apenas iOS. Recriar telas, lógica, serviços e comportamento continua sendo trabalho de desenvolvimento específico da plataforma.

Além dos pacotes públicos: 14 testes automatizados passam, incluindo caminhos maliciosos, CRC de recurso corrompido, Info.plist inválido e preservação do original; 200 manifestos Android e 300 Info.plist aleatórios/malformados produziram somente relatórios ou erros controlados.

## Versão 0.5.0 — plano estruturado de reconstrução

- O ensaio com o APK F-Droid gerou o ZIP iOS com plano JSON/Markdown: pacote `org.fdroid.fdroid`, 490 recursos candidatos copiados, dez caminhos colidentes informados; o ZIP passou na verificação de integridade.
- O ensaio com o IPA de desenvolvimento Sheaf gerou o ZIP Android com plano JSON/Markdown: pacote `systems.lupine.sheaf`, sete recursos candidatos copiados, nenhum item ignorado; o ZIP passou na verificação de integridade.
- Os dois planos contêm evidências extraídas e seis tarefas de reconstrução ainda pendentes. Isso organiza o trabalho humano; não implementa telas, serviços ou comportamento.
- Quando há indício de uma funcionalidade conhecida, o plano sugere uma API nativa de destino para pesquisa (por exemplo, câmera AndroidX CameraX ou iOS AVFoundation). A sugestão não gera código, permissão nem configuração de plataforma.
- A interface passou a chamar a ação de “Gerar plano de reconstrução” e avisa quais arquivos vêm no ZIP e que não é instalável.
- Os 14 testes automatizados e a compilação de bytecode passaram após as mudanças, incluindo uma verificação do mapeamento de câmera para API iOS.
- A GUI empacotada abriu e exibiu o título esperado. A compilação dos projetos Android/iOS não foi executada: faltam Gradle/Android SDK no PC e o Xcode só funciona em macOS.

## Versão 0.6.0 — importação de imagens em recursos nativos

- A tentativa APK F-Droid → iOS integrou 103 imagens PNG/JPEG em `Assets.xcassets`, com 103 catálogos `Contents.json` válidos, nomes sem colisão e ligação do catálogo ao projeto Xcode. Um SVG permaneceu na área de revisão e foi relatado, pois a versão atual não o integra automaticamente ao catálogo iOS.
- A tentativa IPA Sheaf → Android não encontrou imagem raster elegível entre os candidatos selecionados; o mapa informa zero imagens, sem fabricar cópias. A pasta `drawable-nodpi` é gerada quando existem imagens compatíveis.
- `native-resource-map.json` relaciona cada caminho de origem ao caminho do projeto e dá uma sugestão de chamada (`Image("nome")` ou `R.drawable.nome`). As imagens ficam empacotadas, mas não são ligadas ao placeholder da tela.
- Ambos os ZIPs passaram `ZipFile.testzip()`, caminhos mapeados existem, e o original APK/IPA mantém o SHA-256 previamente documentado.
- 16 testes automatizados passaram, incluindo assinatura/dimensões de PNG, nomes duplicados normalizados e saída para as duas plataformas.

## Versão 0.7.0 — recuperação estática de APK com JADX

- O JADX 1.5.6 Windows com JRE incluído foi baixado da release oficial. O SHA-256 local `56A870460D03D3D6F22EB0908C33E298BC7370C952A6B7FA48C22A187ECD690B` confere com o digest publicado pela API oficial da release. A licença Apache 2.0 e os avisos do runtime são distribuídos junto à ferramenta.
- No APK oficial F-Droid 2.0.3, a execução integrada recuperou 11.951 arquivos Java, 677 XML e 183 imagens. O JADX terminou com código 3 e reportou 147 erros; a aplicação classificou o resultado como parcial e deixou o log e o relatório junto à saída.
- No APK oficial NewPipe 0.29.1, recuperou 7.095 arquivos Java, 951 XML e 394 imagens; reportou 117 erros e código 3. Para evitar colisões em diretórios sem distinção de maiúsculas/minúsculas, a entrada filtrou e listou 109 caminhos de recursos; isso deixa a recuperação incompleta. O inventário XML reconheceu 187 layouts, 14 menus e até 5.000 strings/localizações, sem localizar grafo XML de navegação.
- O `decompilation-report.json` guardou o mesmo SHA-256 antes e depois: `DAC55A0D17B1EDF7E7286B48CFBD70C7C52FBB32A00AF062C68830A437C47959`. O APK foi processado somente como dado e não foi instalado nem executado.
- Os 21 testes cobrem chamada sem shell, somente APK, ausência da ferramenta, resultado parcial, timeout, filtragem de entrada ZIP path traversal, inventário de layout/menu/navegação/strings e paths absolutos quando a pasta de saída é informada relativamente.
- A saída é Java aproximado para referência. Ela não recupera o código original, não converte para Swift e não prova que telas ou comportamento estejam corretos.
- O executável Windows abriu e o JADX/JRE contidos na distribuição responderam à chamada CLI `--help`. A distribuição ZIP final inclui ferramentas/licenças e não contém os APKs/IPAs de teste; a integridade passou na verificação de entrega.

## Versão 0.8.0 — prévia SwiftUI de layouts Android

- Gerador percorreu os recursos já recuperados do APK oficial NewPipe: 100 layouts (limite da prévia), 553 nós XML e 33 tipos de widget deixados explicitamente como placeholders, em arquivo Swift de 71.502 bytes.
- Hash do APK de origem lido: `18447bfb1e06d113edc88df93f471827280de06f6f3d4dc42f56f28b9c1bab79`; esta etapa atuou sobre a saída de recuperação existente e não modificou o APK.
- A suíte automatizada cobre o mapeamento de texto/botão, string resource, widget desconhecido e a integração do arquivo Swift e relatório JSON na recuperação.
- Um teste de integração confirma que a recuperação cria projeto Xcode-base e liga a prévia gerada como tela raiz no `App.swift`; a integração real NewPipe também confirmou `PortabilityStarter.xcodeproj`, raiz `ReconstructedPreview()` e um único `import SwiftUI`.
- A prévia não foi compilada: Xcode/iOS SDK exigem macOS. Ela não implementa comportamento e não representa conversão funcional para iOS.
- Build PyInstaller 6.22.3 concluiu; abertura do executável GUI foi confirmada. JADX/JRE já validados foram empacotados junto do EXE.
- `python -m unittest discover -s tests -v`: 22 testes passaram; `python -m compileall -q cpc tests`: passou.
- Distribuição `CrossPlatformAppConverter-0.8.0-Windows.zip`: 1147 entradas; `ZipFile.testzip()` retornou `None`; EXE, JADX JAR, README e avisos de terceiros presentes; nenhum APK/IPA incluído. Tamanho 111.987.587 bytes. SHA-256 `c10f90b8c0daebbd379c858f59ef4e306e7a75b3f0775716f6bdade8993c1ac7`.

## Versão 0.9.0 — catálogo navegável de layouts

- Teste de unidade atualizado com duas variantes de layout (`layout` e `layout-land`): ambas devem ter linhas `NavigationLink` e nomes de tipos Swift únicos.
- Nos recursos NewPipe recuperados, o catálogo contém 100 links para 100 structs geradas (limite da prévia); 87 layouts adicionais ficam fora deste limite. O projeto-base usa o catálogo como tela raiz.
- Mesmo SHA-256 da amostra NewPipe antes/depois: `18447bfb1e06d113edc88df93f471827280de06f6f3d4dc42f56f28b9c1bab79`.
- A interface continua uma referência visual aproximada; não replica fluxo/navegação Android, ações, estado ou componentes não mapeados.
- O catálogo real NewPipe contém 100 links correspondentes a 100 structs geradas; todos os nomes Swift são únicos. A amostra manteve o SHA-256 original antes/depois.
- `python -m unittest discover -s tests -v`: 22 testes passaram; `python -m compileall -q cpc tests`: passou.
- Build PyInstaller 6.22.3 concluiu e a GUI iniciou. ZIP `CrossPlatformAppConverter-0.9.0-Windows.zip`: 1.147 entradas; `ZipFile.testzip()` retornou `None`; EXE, JADX, README e avisos de terceiros presentes; sem APK/IPA. 111.987.833 bytes; SHA-256 `9f98935fac7171e8b6c3c077ddd9f242c4346ccebbaeb3bd889a8cf7275fceba`.

## Versão 0.10.0 — índice de uso de layouts no Java recuperado

- Teste automatizado usa um arquivo Java sintético para conferir a associação de `R.layout.home` à classe `HomeActivity`, enquanto mantém layout sem referência com lista vazia.
- No NewPipe recuperado, examinou 7.094 arquivos Java e encontrou 91 referências registradas para 84 dos 100 nomes de layout atualmente catalogados. O mapa armazena caminho do Java e primeira classe declarada; referências de adapter, diálogo ou código sem execução são possíveis.
- SHA-256 do APK antes e depois segue igual: `18447bfb1e06d113edc88df93f471827280de06f6f3d4dc42f56f28b9c1bab79`.
- `python -m unittest discover -s tests -v`: 23 testes passaram; `python -m compileall -q cpc tests`: passou.
- Build PyInstaller 6.22.3 concluiu e a GUI iniciou. ZIP `CrossPlatformAppConverter-0.10.0-Windows.zip`: 1.147 entradas; `ZipFile.testzip()` retornou `None`; EXE, JADX, README e avisos de terceiros presentes; sem APK/IPA. 111.991.098 bytes; SHA-256 `d43337d0a44e17a1295ce24800162fd1d11cc4e52d8b89dfe23efa5d05ba4263`.

## Versão 0.11.0 — imagens recuperadas no projeto Xcode

- Teste sintético com projeto em caminho profundo confere importação para `Assets.xcassets`, mapa de origem, existência do conteúdo, limite de caminho e que a imagem de origem permanece inalterada.
- Na saída NewPipe já recuperada, 394 imagens drawable/mipmap foram copiadas para revisão e integradas em 394 image sets Xcode; zero ignoradas. Todos os arquivos mapeados existem e os 394 `Contents.json` apontam para seu arquivo de imagem.
- SHA-256 do APK público antes e depois: `18447bfb1e06d113edc88df93f471827280de06f6f3d4dc42f56f28b9c1bab79`.
- As imagens não foram ligadas a views nem visualmente validadas.
- `python -m unittest discover -s tests -v`: 24 testes passaram; `python -m compileall -q cpc tests`: passou.
- Build PyInstaller 6.22.3 concluiu e a GUI iniciou. ZIP `CrossPlatformAppConverter-0.11.0-Windows.zip`: 1.147 entradas; `ZipFile.testzip()` retornou `None`; EXE, JADX, README e avisos de terceiros presentes; sem APK/IPA. 111.995.692 bytes; SHA-256 `632370bfefd59f12cf08c8ee6587a1ef049a9d2522561ef6ae592550179904c0`.
- Caminho inverso, IPA oficial Hiddify 5.5.5 → Android: analisou 396 candidatos, copiou 396, reportou zero ignorados e integrou 10 PNG/JPEG ao `drawable-nodpi`. O ZIP de tentativa passou CRC (`testzip() == None`), seus dez destinos existem e todos os cabeçalhos de imagem correspondem ao formato. ZIP SHA-256 `acc5f87b63b83da1b92c12aa8c97fcefde4f00c70b791d76ca4fa3b4ab080696`. O IPA permaneceu com SHA-256 `55c3712ad89fae1b9ba0421e06b19a6404f896d52ba4a2c9fd16c294216294d0` antes/depois.

## Versão 0.12.0 — falhas isoladas na integração de assets

- Teste injeta erro de escrita após gravar bytes parciais e confirma limpeza/continuação para Android e iOS: o primeiro asset é relatado como não integrado e o segundo continua até o destino.
- `python -m unittest discover -s tests -v`: 25 testes passaram; `python -m compileall -q cpc tests`: passou.
- Novo ensaio IPA público Hiddify após o mecanismo de cópia exclusivo: 396 recursos candidatos copiados, zero ignorados, dez imagens Android integradas; todos os caminhos existem, ZIP CRC válido, hash do IPA idêntico antes/depois. ZIP do projeto-base SHA-256 `2db429bd0920a60975f12f36f1a7e4572258be2ba880f0d290a3a2f953af7e0e`.
- Build PyInstaller 6.22.3 concluiu e a GUI iniciou. ZIP `CrossPlatformAppConverter-0.12.0-Windows.zip`: 1.147 entradas; `ZipFile.testzip()` retornou `None`; EXE, JADX, README e avisos de terceiros presentes; sem APK/IPA. 111.996.111 bytes; SHA-256 `bfd45a8416e4f25e814f60c5a41264be0ec64ad34d74caba2827bdacca549e64`.

## Versão 0.13.0 — revisão de aviso e compilação Android

- Aviso de limitações adicionado à janela principal, ao README e à documentação de validação: podem existir erros/bugs, omissões ou saída que não funciona; revisar, compilar e testar antes de publicar.
- O manifesto gerado Android deixou de emitir o atributo `package` obsoleto. Um teste automatizado exige que o identificador esteja no `namespace` do Gradle e ausente do manifesto.
- `python -m unittest discover -s tests -v`: 25 testes aprovados; `python -m compileall -q cpc tests run_gui.py run_cli.py`: aprovado.
- Cinco amostras oficiais: F-Droid APK, NewPipe APK, Hiddify APK, Sheaf IPA e Hiddify IPA. Cada tentativa criou ZIP com CRC íntegro; SHA-256 de cada origem permaneceu idêntico antes/depois. Hiddify IPA → Android copiou 396 candidatos (10 imagens nativas elegíveis); Sheaf IPA → Android copiou um candidato e deixou seis para revisão; amostras APK → iOS copiaram entre 466 e 486 candidatos e listaram colisões/itens ignorados conforme relatório. Isso valida o processamento dessas entradas, não equivalência do aplicativo.
- APK-base Android gerado do Hiddify IPA compilado com Temurin JDK 17.0.21+9, Gradle 8.9, API 35 e Build Tools 35.0.0. `assembleDebug` concluiu; `aapt dump badging` confirmou `apple.hiddify.com`, `minSdk 23`, `targetSdk 35` e `MainActivity` lançável. A primeira compilação mostrou aviso de manifesto obsoleto; após a correção do gerador, a compilação foi repetida com sucesso. A ferramenta de SDK também avisou diferença de versão do formato XML entre command-line tools e metadados do SDK, sem impedir a compilação.
- O APK gerado não foi executado em emulador/dispositivo. A saída é uma tela placeholder e não implementa Hiddify. O projeto Xcode/SwiftUI não foi compilado; Xcode requer macOS.
- Downloads de validação, mantidos localmente em `work/`: Temurin JDK SHA-256 `98518ecf554465057ee5509462631deeee374bc368c12a411d225cd29381f84b`; Android command-line tools SHA-256 `90ae805d20434428bffcb699c290860f19bb5f66a67e6b330067e3de801fb04a`; Gradle 8.9 SHA-256 `d725d707bfabd4dfdc958c624003b3c80accc03f7037b5122c4b1d0ef15cecab`. Os dois primeiros conferem com as fontes oficiais dos respectivos projetos; o checksum Gradle confere com a referência oficial de checksums.
- Executável GUI da v0.13.0 abriu e permaneceu ativo durante a verificação; o pedido de fechar a janela terminou normalmente. ZIP `CrossPlatformAppConverter-0.13.0-Windows.zip` em Downloads: 1.148 entradas, CRC íntegro, aviso/README/EXE/JADX presentes e nenhum APK/IPA de amostra; 112.056.632 bytes; SHA-256 `4EFA3682DCA1BDD83906C63C4934DD4D9281D76AE0098DD64710FF7BBFF44089`.
- Uma tentativa Hiddify IPA → Android refeita após adicionar o aviso à saída criou ZIP íntegro, incluiu o texto “O conversor não é milagroso” e manteve o SHA-256 da origem `55c3712ad89fae1b9ba0421e06b19a6404f896d52ba4a2c9fd16c294216294d0`.

## Versão 0.14.0 — instalador Windows x64

- O programa agora é distribuído como `CrossPlatformAppConverter-0.14.0-Windows-Setup.exe`. O assistente informa que a instalação requer permissão administrativa, usa `Program Files` como destino padrão, mostra o aviso experimental e exibe a lista completa de arquivos e pastas antes de instalar. Os nomes também aparecem durante o progresso.
- O instalador cria atalho no menu Iniciar e entrada de desinstalação; o desinstalador remove apenas os arquivos que o Setup instalou. O assistente recusa Windows de 32 bits, pois o executável distribuído é x64.
- Teste de interface percorreu as páginas e confirmou 1.206 itens na lista, incluindo o executável e o JADX. Teste isolado copiou os 1.145 arquivos de payload e o desinstalador para uma pasta temporária; a desinstalação removeu toda a pasta, com código de saída 0.
- `build_installer.ps1` automatiza o build do aplicativo e Setup. NSIS 3.13 é baixado para `work/` e conferido pelo SHA-256 oficial `ba63dffc4410ee89193e1cb5a41989991bd77c61068da17e3156d136b7b0b3d8`. A ferramenta de build NSIS não é incluída no instalador.
- O instalador não é assinado digitalmente; Windows pode avisar que o editor é desconhecido. O Setup serve apenas para instalar o conversor. Ele não remove o ZIP experimental de reconstrução e não passa a gerar APK/IPA funcional.
- 25 testes automatizados e `compileall` passaram antes do build final. O executável Setup em Downloads tem 111.013.396 bytes e SHA-256 `6E2BF6268C656A2382EEF79DE2220FF95A5B0262679AE2030339C325EEC8FE57`.

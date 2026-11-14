# Estado do projeto — v0.15.0 experimental

Aviso de publicação: o conversor não é milagroso. Análises, recursos importados e projetos-base podem conter erros ou bugs, omitir partes e até gerar um app que não funciona. Não há conversão funcional garantida de APK/IPA arbitrário. Revise, compile e teste cada saída na plataforma de destino.

## Implementado

- Leitura estática de APK e IPA sem extração.
- Metadados de Android AXML e iOS `Info.plist`.
- Inventário de componentes, permissões, extensões, frameworks, bibliotecas e candidatos a recursos.
- Comparação por indícios, resumo de dificuldade heurístico e ressalvas explícitas.
- Exportação HTML/JSON, GUI Tkinter, CLI e geração de esqueletos experimentais.
- Testes automatizados com arquivos de pacote sintéticos.
- Executável Windows em distribuição de uma pasta; GUI atual abriu, analisou o par Hiddify e gerou o ZIP experimental pela janela.
- Botão experimental de tentativa de portabilidade: cria projeto-base, copia candidatos a recursos com limites e gera um ZIP claramente identificado como não instalável.
- Validação estática com APK oficial do F-Droid e IPA oficial de desenvolvimento do Sheaf; arquivos de teste permanecem fora da distribuição.
- Validação adicional com APK arm64 e IPA da mesma release Hiddify 5.5.5, conferindo os dois hashes publicados pelo GitHub.
- Identificação do executável principal de IPA e seleção de metadados do app diretamente em `Payload`, separando apps watchOS aninhados.
- Catálogos Apple `.car` são relatados como compilados e não extraídos, para deixar visível esse limite de recursos.
- Tentativa de recursos agora detecta colisões após normalização e caminhos perigosos do Windows sem interromper a cópia dos demais itens.
- Bibliotecas `.so` repetidas por arquitetura são agrupadas por nome com as variantes ABI informadas.
- Comparação de frameworks normaliza nomes de frameworks Apple e runtime equivalente para reduzir divergências por sufixo.
- CLI exibe corretamente caracteres portugueses em saída redirecionada; manifestos XML com DTD/entidades são rejeitados e caminhos de dispositivos reservados do Windows são ignorados.
- Info.plist com raiz inesperada ou `UIDeviceFamily` malformado agora é rejeitado/relatado de forma controlada.
- Cópia de recursos descarta links simbólicos do ZIP e não interrompe a tarefa quando um membro está corrompido.
- Erros XML internos ao ler `Info.plist` são convertidos em erro de análise compreensível.
- Cada projeto-base inclui `migration-plan.json` com evidências extraídas e `MIGRATION-PLAN.md` com tarefas explícitas para telas, comportamento, serviços, dependências, permissões, assinatura e testes.
- O plano associa indícios de funcionalidades a APIs nativas candidatas para Android/iOS (câmera, localização, notificações, Bluetooth, contatos, saúde, pagamentos, biometria e segundo plano); são referências para revisão, não implementações automáticas.
- A GUI nomeia o recurso como plano de reconstrução e descreve no aviso o conteúdo gerado e o que permanece por implementar.
- Tentativas de portabilidade integram imagens com cabeçalhos reconhecidos em `Assets.xcassets` (iOS) ou `drawable-nodpi` (Android), dão nomes de recurso seguros, criam o vínculo do catálogo Xcode e emitem `native-resource-map.json` com caminhos e sugestões de uso.
- As imagens continuam também em `imported_resources`; imagens sem cabeçalho reconhecido, extensões incompatíveis ou não imagens não entram no bundle nativo. Nenhuma imagem é redimensionada ou ligada automaticamente à tela.
- Recuperação experimental de APK integrada via JADX 1.5.6 com JRE portátil: exporta Java aproximado e recursos decodificados para diretório sem colisão; gera README, log e JSON com hashes antes/depois, contagens e erros reportados.
- Analisa XML recuperado para criar `android-ui-inventory.json`: resume layouts e tipos de views, menus, grafos de navegação declarados e textos de recursos, sem afirmar que capturou toda a interface.
- CLI tem `--recover-apk`; GUI tem botão equivalente para APK. IPA é recusado nessa operação e permanece no fluxo de análise estática/recursos.
- Processo JADX usa argumentos sem shell, entrada padrão fechada, duas tarefas, teto de heap Java de 2 GB e timeout de 30 minutos; APK nunca é instalado nem executado.
- Release oficial da ferramenta conferida por SHA-256 antes de distribuir; licença Apache 2.0 e avisos do runtime acompanham a ferramenta.
- Recuperação APK gera projeto-base Xcode que abre a prévia `ReconstructedPreview` embutida em `App.swift`, com o arquivo-fonte separado `swiftui-layout-preview.swift` e relatório `swiftui-preview-report.json`. Ações, estado, navegação, APIs e widgets dinâmicos continuam sem portabilidade.
- A prévia v0.9 ganhou catálogo SwiftUI com navegação para cada layout XML gerado (incluindo qualifiers como `layout-land`); não presume que todos os layouts representem telas distintas do fluxo original.
- O relatório `android-layout-source-map.json` associa nomes dos layouts à ocorrência estática de `R.layout` em fontes Java recuperados; registra arquivo/classe candidata e os limites de inspeção, sem alegar fluxo ativo.
- As imagens raster de `res/drawable*`/`res/mipmap*` recuperadas são copiadas à pasta de revisão do esqueleto iOS e as compatíveis entram em `Assets.xcassets`; `native-resource-map.json` relaciona origem/destino. Elas não são ligadas a telas sem evidência semântica.
- Falhas na gravação de um asset nativo agora são registradas como não integrado, removem qualquer arquivo parcial criado pela operação e deixam a integração dos demais recursos continuar.
- A janela principal e o README exibem um aviso direto de que o resultado pode conter erros/bugs ou não funcionar.
- O manifesto Android gerado não declara mais o atributo `package` obsoleto; o identificador fica em `namespace` no Gradle.
- Instalador Windows x64 de arquivo único com aviso, destino padrão em `Program Files`, lista prévia de arquivos/pastas, progresso detalhado, atalho no menu Iniciar e desinstalador.
- O Setup instala o conversor; ele não cria APK/IPA funcional. As tentativas de reconstrução dentro do programa continuam experimentais e podem gerar ZIPs com esqueletos.
- Testes de instalação/desinstalação e da página com 1.206 itens passaram em modo de teste local. Executável Setup criado em Downloads; não assinado digitalmente.

## Experimental

- Detecção de dependências e recursos por nomes de arquivos.
- Pontuação de dificuldade.
- Esqueletos de projeto Android e iOS, não validados por compilação nesta máquina.
- Mapeamento de recursos por extensão/nome; recursos importados podem ser irrelevantes ou incompletos. Validação de imagens verifica apenas cabeçalhos e dimensões PNG, sem decodificação visual completa.
- Plano de reconstrução reúne evidências estáticas, mas os nomes e componentes ainda precisam ser confirmados manualmente; não há análise de fluxo de telas nem tradução de lógica.
- JADX pode reportar erro e produzir código parcial, ofuscado ou incorreto. O código recuperado não é o original e não é convertido em Swift nem compilado automaticamente.
- A prévia SwiftUI é somente uma referência de interface: até 100 layouts e 5.000 nós; widgets dinâmicos ficam como placeholders; não foi compilada por falta de Xcode/macOS.
- Validação com três apps e um par da mesma versão; não representa todos os formatos, lojas ou aplicativos.

## Não implementado

- Conversão direta de binários Android para iOS ou vice-versa.
- Geração de APK/IPA instalável ou recriação automática da lógica/telas do app.
- Recuperação de código-fonte, decompilação, execução em emulador, compilação, assinatura ou publicação.
- Garantia de que duas versões do app tenham o mesmo comportamento.
- Recuperação equivalente de código-fonte de IPA/Swift e tradução automática Java/Kotlin → Swift.

## Verificação desta entrega

- `python -m unittest discover -s tests -v`: 25 testes aprovados na versão 0.12.0.
- `python -m compileall -q .`: passou.
- Ensaio adicional: 200 manifestos APK aleatórios/malformados terminaram em relatório ou erro controlado, sem exceção inesperada.
- Ensaio adicional: 300 `Info.plist` aleatórios/malformados terminaram em relatório ou erro controlado, sem exceção inesperada.
- GUI empacotada: abriu no Windows, analisou um APK e um IPA reais da mesma versão, exibiu a comparação e criou o rascunho pela interface.
- A compilação iOS do esqueleto não pôde ser executada porque Xcode requer macOS.
- v0.5.0: 14 testes aprovados após adicionar e verificar plano estruturado, referências de API por funcionalidade e ZIPs de tentativa.
- v0.6.0: 16 testes aprovados, incluindo integração de PNG em catálogo Xcode e `drawable-nodpi`, nomes seguros em colisões e vínculo do catálogo no projeto Xcode.
- Amostra real: tentativa APK F-Droid → iOS integrou 103 imagens e gerou 103 `Contents.json` válidos; tentativa IPA Sheaf → Android registrou zero imagem elegível. Ambos os ZIPs passaram na integridade e os hashes dos originais permaneceram iguais aos hashes registrados.
- Limite de compilação: este Windows não tem Android SDK/Gradle instalado e possui apenas Java 8; não foi possível compilar o projeto-base Android. Xcode requer macOS para compilar iOS.
- JADX 1.5.6 oficial portátil (SHA-256 do ZIP: `56A870460D03D3D6F22EB0908C33E298BC7370C952A6B7FA48C22A187ECD690B`) recuperou do APK F-Droid 11.951 arquivos Java, 677 XML e 183 imagens, mas reportou 147 erros e código de processo 3. Isso foi classificado como resultado parcial, não sucesso completo. O SHA-256 do APK antes/depois permaneceu igual.
- No NewPipe, 109 entradas com nomes que colidem no Windows por diferença de maiúsculas/minúsculas foram omitidas da cópia de trabalho; seus nomes constam no relatório. O resultado recuperou 7.095 arquivos Java, 951 XML e 394 imagens, mas reportou 117 erros. O SHA-256 do original permaneceu igual.
- v0.7.0: 21 testes passaram, incluindo erros parciais do JADX, timeout com saída preservada, filtragem de ZIP path traversal, parsing seguro do inventário XML e caminhos relativos.
- Distribuição Windows final: o executável e o JADX/JRE incluídos iniciaram; o ZIP final passou na verificação de integridade, contém ferramenta/licenças e não contém APK/IPA de amostra.
- v0.8.0: 22 testes e compileall passaram; a recuperação real NewPipe preservou o hash do APK e criou projeto Xcode-base com 100 previews, 553 nós e 33 tipos sem mapeamento; a GUI compilada iniciou; ZIP Windows verificado com 1.147 entradas, CRC íntegro, EXE/JADX/licenças/docs presentes e nenhum APK/IPA. SHA-256 `c10f90b8c0daebbd379c858f59ef4e306e7a75b3f0775716f6bdade8993c1ac7`.
- v0.9.0: catálogo SwiftUI navegável; nos 100 layouts incluidos do NewPipe foram gerados 100 links, 100 views e nomes únicos; hash original preservado. 22 testes passaram e a GUI compilada iniciou. ZIP Windows com 1.147 entradas, CRC válido, docs/licenças/EXE/JADX e sem APK/IPA; SHA-256 `9f98935fac7171e8b6c3c077ddd9f242c4346ccebbaeb3bd889a8cf7275fceba`.
- v0.10.0: índice Java `R.layout` adicionado; a amostra NewPipe encontrou referências em 84 dos 100 layouts catalogados após examinar 7.094 fontes. 23 testes passaram, compileall passou e a GUI compilada iniciou. ZIP verificado com 1.147 entradas, CRC íntegro, docs/licenças/EXE/JADX e sem APK/IPA; SHA-256 `d43337d0a44e17a1295ce24800162fd1d11cc4e52d8b89dfe23efa5d05ba4263`.
- v0.11.0: NewPipe integrou 394/394 imagens raster elegíveis no catálogo Xcode, sem caminhos ausentes nem `Contents.json` inválidos; SHA do APK preservado. 24 testes e compileall passaram; GUI compilada iniciou. ZIP validado com 1.147 entradas, CRC íntegro, docs/licenças/EXE/JADX e sem APK/IPA; SHA-256 `632370bfefd59f12cf08c8ee6587a1ef049a9d2522561ef6ae592550179904c0`.
- Validação complementar IPA Hiddify 5.5.5 → Android integrou 10 imagens raster em `drawable-nodpi`; 396 recursos candidatos copiados, zero ignorados, ZIP íntegro e SHA do IPA preservado.
- v0.12.0: erros simulados de gravação em assets Android/iOS são isolados e arquivos parciais limpos. 25 testes e compileall passaram; GUI compilada iniciou. Reensaio IPA público Hiddify manteve 10 assets Android, ZIP válido e SHA do original preservado. ZIP Windows tem 1.147 entradas, CRC íntegro, docs/licenças/EXE/JADX e nenhum APK/IPA; SHA-256 `bfd45a8416e4f25e814f60c5a41264be0ec64ad34d74caba2827bdacca549e64`.
- v0.13.0: 25 testes, compileall, análise e tentativa de portabilidade com cinco amostras públicas APK/IPA; todos os ZIPs passaram CRC e os hashes dos pacotes originais permaneceram iguais. Projeto Android-base gerado do IPA Hiddify compilou com Gradle 8.9, JDK 17.0.21+9 e Android API 35/Build Tools 35; `aapt dump badging` confirmou pacote e atividade inicializável. Não foi executado em emulador/dispositivo. Xcode/iOS continua sem compilação por exigir macOS.
- ZIP Windows v0.13.0 criado e verificado em Downloads; contém EXE, README e JADX, sem APK/IPA de amostra. CRC do ZIP íntegro, aviso de limitações incluído e GUI abriu no Windows.

## Atualização 0.15.0 — idioma e tema do Windows

- A interface escolhe português quando o idioma de exibição do Windows é português e usa inglês nos demais casos. O resumo da análise e as mensagens principais também acompanham o idioma; o conteúdo dos pacotes e alguns detalhes técnicos continuam no idioma original.
- A interface aplica o tema claro/escuro configurado no Windows e acompanha mudanças feitas enquanto está aberta. Se a preferência não puder ser lida, usa o tema claro.
- O instalador contém português brasileiro e inglês e seleciona o idioma compatível com o Windows.
- 25 testes automatizados passaram; `py_compile` passou; o executável Windows compilado abriu nesta máquina, que detectou português e tema escuro.
- O instalador 0.15.0 foi compilado com sucesso e copiado para Downloads. SHA-256: `60ACF7FF5D8017376AC4AF47F2AB0ED2696AA5567C819B1E7AF9C3F48FF17319`.
- A mudança não traduz APKs/IPAs nem afeta os projetos-base gerados. Idiomas além de português usam inglês; a detecção de idioma foi conferida neste computador em português, sem teste em Windows configurado em inglês.

# Avisos de componentes de terceiros

## JADX 1.5.6

- Uso: recuperação experimental de Java aproximado e recursos Android a partir de APK.
- Projeto e código-fonte: https://github.com/skylot/jadx
- Release oficial: https://github.com/skylot/jadx/releases/tag/v1.5.6
- Arquivo Windows portátil com runtime Java: `jadx-gui-1.5.6-with-jre-win.zip`.
- SHA-256 conferido contra a API da release oficial: `56A870460D03D3D6F22EB0908C33E298BC7370C952A6B7FA48C22A187ECD690B`.
- Licença do JADX: Apache License 2.0; cópia em `JADX-LICENSE.txt` na pasta da ferramenta distribuída.
- O JRE incluído mantém os avisos e arquivos legais na subpasta `jre/legal`.

O JADX pode deixar código sem decompilar ou reconstruí-lo incorretamente. O resultado não é código-fonte original, não é convertido para iOS e não é executado pelo CrossPlatform App Converter. Consulte a release e os arquivos de licença incluídos antes de redistribuir o pacote.

## NSIS 3.13

- Uso: criação do instalador Windows de arquivo único.
- Projeto: https://nsis.sourceforge.io/
- Licenças: o NSIS usa principalmente zlib/libpng; componentes de compressão podem ter termos próprios. O instalador usa a compressão zlib do NSIS. Consulte a licença oficial antes de redistribuir: https://nsis.sourceforge.io/License.
- A ferramenta NSIS não é instalada no computador de quem usa o conversor; seus componentes necessários ao instalador ficam incorporados ao executável Setup.

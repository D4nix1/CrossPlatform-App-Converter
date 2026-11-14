Unicode true

!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "WinMessages.nsh"
!include "x64.nsh"

!ifndef APP_DIR
  !error "APP_DIR must point to the PyInstaller application folder"
!endif
!ifndef APP_VERSION
  !define APP_VERSION "0.15.0"
!endif
!ifndef MANIFEST_FILE
  !error "MANIFEST_FILE must point to the generated install manifest"
!endif
!ifndef UNINSTALL_LIST
  !error "UNINSTALL_LIST must point to the generated uninstall list"
!endif
!ifndef OUTPUT_FILE
  !error "OUTPUT_FILE must point to the setup executable"
!endif

!define APP_NAME "CrossPlatform App Converter"
!define APP_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\CrossPlatformAppConverter"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_RUN "$INSTDIR\CrossPlatformAppConverter.exe"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "${OUTPUT_FILE}"
!ifdef TEST_MODE
  !define APP_REG_ROOT HKCU
  InstallDir "$LOCALAPPDATA\CrossPlatformAppConverter-Installer-Test"
  RequestExecutionLevel user
!else
  !define APP_REG_ROOT HKLM
  InstallDir "$PROGRAMFILES64\CrossPlatformAppConverter"
  RequestExecutionLevel admin
!endif
InstallDirRegKey ${APP_REG_ROOT} "${APP_KEY}" "InstallLocation"
SetCompressor zlib
ShowInstDetails show
ShowUnInstDetails show
VIProductVersion "0.15.0.0"
VIAddVersionKey "ProductName" "${APP_NAME}"
VIAddVersionKey "ProductVersion" "${APP_VERSION}"
VIAddVersionKey "FileDescription" "Instalador do ${APP_NAME}"
VIAddVersionKey "FileVersion" "${APP_VERSION}"
VIAddVersionKey "LegalCopyright" "CrossPlatform App Converter contributors"

!insertmacro MUI_PAGE_WELCOME
Page custom NoticePage
!insertmacro MUI_PAGE_DIRECTORY
Page custom ContentsPage
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "PortugueseBR"

LangString STR_NOTICE_TITLE ${LANG_ENGLISH} "Important notice"
LangString STR_NOTICE_SUBTITLE ${LANG_ENGLISH} "Read before installing"
LangString STR_NOTICE_BODY ${LANG_ENGLISH} "Notice: this converter is not magic. Analysis and starter projects may contain errors or bugs, omit parts, or result in an app that does not work. It does not automatically create equivalent functional APKs/IPAs. Review, build, and test outputs before publishing."
LangString STR_CONTENTS_TITLE ${LANG_ENGLISH} "Installation files"
LangString STR_CONTENTS_SUBTITLE ${LANG_ENGLISH} "Review the destination and items to be installed"
LangString STR_DESTINATION ${LANG_ENGLISH} "Destination"
LangString STR_SECTION ${LANG_ENGLISH} "Application"
LangString STR_X64 ${LANG_ENGLISH} "This installer requires 64-bit Windows."
LangString STR_NOTICE_TITLE ${LANG_PORTUGUESEBR} "Aviso importante"
LangString STR_NOTICE_SUBTITLE ${LANG_PORTUGUESEBR} "Leia antes de instalar"
LangString STR_NOTICE_BODY ${LANG_PORTUGUESEBR} "Aviso: este conversor não é milagroso. As análises e os projetos-base podem conter erros ou bugs, omitir partes e até resultar em um app que não funciona. Ele não cria automaticamente APKs/IPAs funcionais equivalentes. Revise, compile e teste as saídas antes de publicar."
LangString STR_CONTENTS_TITLE ${LANG_PORTUGUESEBR} "Arquivos da instalação"
LangString STR_CONTENTS_SUBTITLE ${LANG_PORTUGUESEBR} "Confira o destino e os itens que serão instalados"
LangString STR_DESTINATION ${LANG_PORTUGUESEBR} "Destino"
LangString STR_SECTION ${LANG_PORTUGUESEBR} "Aplicativo"
LangString STR_X64 ${LANG_PORTUGUESEBR} "Este instalador requer Windows de 64 bits."

Var NoticeText
Var ContentsText
Var DialogHandle
Var ReadHandle
Var ReadLine

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "$(STR_X64)"
    Abort
  ${EndIf}
  InitPluginsDir
  SetOutPath "$PLUGINSDIR"
  File /oname=install-manifest.txt "${MANIFEST_FILE}"
FunctionEnd

Function NoticePage
  !insertmacro MUI_HEADER_TEXT "$(STR_NOTICE_TITLE)" "$(STR_NOTICE_SUBTITLE)"
  nsDialogs::Create 1018
  Pop $DialogHandle
  nsDialogs::CreateControl EDIT "${DEFAULT_STYLES}|${WS_TABSTOP}|${ES_MULTILINE}|${ES_AUTOVSCROLL}|${WS_VSCROLL}" "${WS_EX_WINDOWEDGE}|${WS_EX_CLIENTEDGE}" 0 0 100% 100u ""
  Pop $NoticeText
  ${NSD_SetText} $NoticeText "$(STR_NOTICE_BODY)"
  SendMessage $NoticeText ${EM_SETREADONLY} 1 0
  nsDialogs::Show
FunctionEnd

Function ContentsPage
  !insertmacro MUI_HEADER_TEXT "$(STR_CONTENTS_TITLE)" "$(STR_CONTENTS_SUBTITLE)"
  nsDialogs::Create 1018
  Pop $DialogHandle
  ${NSD_CreateLabel} 0 0 100% 18u "$(STR_DESTINATION): $INSTDIR"
  Pop $0
  nsDialogs::CreateControl EDIT "${DEFAULT_STYLES}|${WS_TABSTOP}|${ES_MULTILINE}|${ES_AUTOVSCROLL}|${WS_VSCROLL}" "${WS_EX_WINDOWEDGE}|${WS_EX_CLIENTEDGE}" 0 22u 100% 190u ""
  Pop $ContentsText
  SendMessage $ContentsText ${EM_SETLIMITTEXT} 1000000 0
  FileOpen $ReadHandle "$PLUGINSDIR\install-manifest.txt" r
  IfErrors contents_done
contents_read:
  ClearErrors
  FileRead $ReadHandle $ReadLine
  IfErrors contents_close
  SendMessage $ContentsText ${EM_SETSEL} -1 -1
  SendMessage $ContentsText ${EM_REPLACESEL} 0 "STR:$ReadLine"
  Goto contents_read
contents_close:
  FileClose $ReadHandle
contents_done:
  SendMessage $ContentsText ${EM_SETREADONLY} 1 0
  nsDialogs::Show
FunctionEnd

Section "$(STR_SECTION)" SecApplication
  SetRegView 64
!ifdef TEST_MODE
  SetShellVarContext current
!else
  SetShellVarContext all
!endif
  SetOutPath "$INSTDIR"
  File /r "${APP_DIR}\*"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\CrossPlatform App Converter"
  CreateShortcut "$SMPROGRAMS\CrossPlatform App Converter\CrossPlatform App Converter.lnk" "$INSTDIR\CrossPlatformAppConverter.exe"
  WriteRegStr ${APP_REG_ROOT} "${APP_KEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr ${APP_REG_ROOT} "${APP_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr ${APP_REG_ROOT} "${APP_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr ${APP_REG_ROOT} "${APP_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr ${APP_REG_ROOT} "${APP_KEY}" "DisplayIcon" "$INSTDIR\CrossPlatformAppConverter.exe"
  WriteRegDWORD ${APP_REG_ROOT} "${APP_KEY}" "NoModify" 1
  WriteRegDWORD ${APP_REG_ROOT} "${APP_KEY}" "NoRepair" 1
SectionEnd

Section "Uninstall"
!ifdef TEST_MODE
  SetShellVarContext current
!else
  SetShellVarContext all
!endif
  SetRegView 64
  Delete "$SMPROGRAMS\CrossPlatform App Converter\CrossPlatform App Converter.lnk"
  RMDir "$SMPROGRAMS\CrossPlatform App Converter"
  !include "${UNINSTALL_LIST}"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey ${APP_REG_ROOT} "${APP_KEY}"
SectionEnd

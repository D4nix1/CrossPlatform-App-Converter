from __future__ import annotations

import ctypes
import locale
import sys
import winreg


def detect_language() -> str:
    """Use the Windows display language where available; support Portuguese and English."""
    language = ""
    if sys.platform == "win32":
        try:
            language = locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), "")
        except (AttributeError, OSError, TypeError):
            pass
    if not language:
        language = locale.getlocale()[0] or ""
    return "pt" if language.lower().startswith("pt") else "en"


def detect_dark_mode() -> bool:
    if sys.platform != "win32":
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
    except (OSError, ImportError):
        return False


TEXT = {
    "pt": {
        "subtitle": "Análise estática e plano de reconstrução. Não traduz nem executa os pacotes.",
        "warning": "Aviso: o conversor não é milagroso. A saída pode conter erros/bugs ou não funcionar; revise, compile e teste antes de publicar.",
        "select": "Selecionar…", "all_files": "Todos os arquivos", "analyze": "Analisar",
        "save": "Salvar relatório JSON + HTML", "target": "Esqueleto para:", "scaffold": "Criar esqueleto experimental",
        "conversion": "Gerar plano de reconstrução", "recover": "Recuperar código APK (experimental)",
        "originals": "Os arquivos originais são lidos sem extração e nunca são alterados.",
        "pick_package": "Selecione um pacote", "pick_package_body": "Escolha um APK, um IPA ou os dois.",
        "reading": "Lendo estrutura e metadados; os pacotes não serão extraídos…", "analysis_failed": "A análise não terminou.",
        "analysis_error": "Erro de análise", "analysis_done": "Análise concluída: {count} pacote(s).",
        "no_analysis": "Sem análise", "analyze_before_save": "Execute uma análise antes de salvar o relatório.",
        "report_folder": "Escolha a pasta dos relatórios", "save_failed": "Não foi possível salvar",
        "reports_saved": "Relatórios salvos", "reports_saved_status": "Relatórios salvos sem substituir arquivos existentes.",
        "no_analysis_scaffold": "Analise um APK ou IPA antes de criar um esqueleto.", "invalid_target": "Destino inválido",
        "opposite_target": "Escolha a plataforma oposta ao pacote de origem.", "scaffold_folder": "Escolha onde criar uma nova pasta do projeto",
        "create_failed": "Não foi possível criar", "scaffold_created": "Esqueleto experimental criado em uma nova pasta.",
        "scaffold_created_title": "Esqueleto criado", "readme_limits": "Consulte o README.md para os limites e passos seguintes.",
        "no_analysis_conversion": "Analise um APK ou IPA antes de tentar a portabilidade.", "conversion_folder": "Escolha onde salvar o pacote de tentativa",
        "creating": "Criando projeto-base e copiando recursos candidatos com limites…", "attempt_failed": "A tentativa não terminou.",
        "attempt_error": "Erro na tentativa", "draft_status": "Rascunho criado; {copied} recurso(s) copiado(s), {skipped} ignorado(s).",
        "draft_title": "Rascunho experimental criado", "draft_body": "Pacote: {bundle}\n\nO ZIP inclui projeto-base, migration-plan.json, MIGRATION-PLAN.md e native-resource-map.json. Imagens compatíveis entram no catálogo nativo, mas não são ligadas à tela de exemplo. O ZIP não é um APK/IPA instalável: telas e comportamento ainda precisam ser reconstruídos, compilados e testados na plataforma-alvo.",
        "no_analysis_recover": "Analise um APK antes de tentar recuperar código aproximado.", "apk_only": "Somente APK",
        "ipa_recovery": "JADX recupera Java aproximado e recursos de APK. Não decompila IPA nem converte Java para Swift.",
        "recovery_folder": "Escolha onde salvar os arquivos recuperados", "recovering": "Tentando recuperar Java aproximado e decodificar recursos; o APK não será executado…",
        "recovery_failed": "A recuperação não terminou.", "recovery_error": "Erro na recuperação",
        "recovery_status": "Recuperação {status}; {java} Java, {xml} XML, {layouts} layouts, {strings} strings, {errors} erro(s), {omitted} entradas omitidas.",
        "recovery_title": "Recuperação aproximada concluída",
        "recovery_body": "Arquivos: {directory}\n\n{java} arquivos Java, {xml} XML, {images} imagens; {layouts} layouts, {strings} strings; JADX relatou {errors} erros e {omitted} entradas do APK foram omitidas antes do processamento.\n\nIsto não é o código-fonte original e não é convertido para iOS. O resultado não foi compilado nem executado; revise README.md, android-ui-inventory.json, decompilation-report.json e jadx.log.",
        "ready_status": "Selecione um APK, um IPA ou os dois para comparar.",
    },
    "en": {
        "subtitle": "Static analysis and a reconstruction plan. Packages are not translated or run.",
        "warning": "Notice: this converter is not magic. Output may contain errors or bugs, or may not work. Review, build, and test it before publishing.",
        "select": "Browse…", "all_files": "All files", "analyze": "Analyze",
        "save": "Save JSON + HTML report", "target": "Create starter for:", "scaffold": "Create experimental starter",
        "conversion": "Create reconstruction plan", "recover": "Recover APK code (experimental)",
        "originals": "Original files are read without extraction and are never changed.",
        "pick_package": "Select a package", "pick_package_body": "Choose an APK, an IPA, or both.",
        "reading": "Reading structure and metadata; packages will not be extracted…", "analysis_failed": "Analysis did not finish.",
        "analysis_error": "Analysis error", "analysis_done": "Analysis complete: {count} package(s).",
        "no_analysis": "No analysis", "analyze_before_save": "Run an analysis before saving a report.",
        "report_folder": "Choose a folder for the reports", "save_failed": "Could not save",
        "reports_saved": "Reports saved", "reports_saved_status": "Reports saved without replacing existing files.",
        "no_analysis_scaffold": "Analyze an APK or IPA before creating a starter project.", "invalid_target": "Invalid destination",
        "opposite_target": "Choose the platform opposite to the source package.", "scaffold_folder": "Choose where to create a new project folder",
        "create_failed": "Could not create", "scaffold_created": "Experimental starter project created in a new folder.",
        "scaffold_created_title": "Starter project created", "readme_limits": "See README.md for limitations and next steps.",
        "no_analysis_conversion": "Analyze an APK or IPA before creating a portability attempt.", "conversion_folder": "Choose where to save the attempt package",
        "creating": "Creating a starter project and copying candidate resources…", "attempt_failed": "The attempt did not finish.",
        "attempt_error": "Attempt error", "draft_status": "Draft created; {copied} resource(s) copied, {skipped} skipped.",
        "draft_title": "Experimental draft created", "draft_body": "Package: {bundle}\n\nThe ZIP contains a starter project, migration-plan.json, MIGRATION-PLAN.md, and native-resource-map.json. Compatible images are added to the native catalog but are not connected to the sample screen. The ZIP is not an installable APK/IPA: screens and behavior still need to be rebuilt, compiled, and tested on the target platform.",
        "no_analysis_recover": "Analyze an APK before attempting approximate code recovery.", "apk_only": "APK only",
        "ipa_recovery": "JADX recovers approximate Java and resources from APKs. It does not decompile IPAs or convert Java to Swift.",
        "recovery_folder": "Choose where to save recovered files", "recovering": "Attempting to recover approximate Java and decode resources; the APK will not be run…",
        "recovery_failed": "Recovery did not finish.", "recovery_error": "Recovery error",
        "recovery_status": "Recovery {status}; {java} Java, {xml} XML, {layouts} layouts, {strings} strings, {errors} error(s), {omitted} entries omitted.",
        "recovery_title": "Approximate recovery complete",
        "recovery_body": "Files: {directory}\n\n{java} Java files, {xml} XML files, {images} images; {layouts} layouts, {strings} strings; JADX reported {errors} errors and {omitted} APK entries were omitted before processing.\n\nThis is not the original source code and is not converted to iOS. The result was not built or run; review README.md, android-ui-inventory.json, decompilation-report.json, and jadx.log.",
        "ready_status": "Select an APK, an IPA, or both to compare.",
        "status_partial_timeout": "partial (timed out)", "status_partial_failure": "partially failed",
        "status_partial_with_decompilation_errors": "partial, with decompilation errors",
        "status_partial_with_entries_omitted": "partial, with APK entries omitted", "status_resources_only": "resources only",
        "status_completed_with_heuristic_source": "completed with approximate code",
    },
}


def strings(language: str) -> dict[str, str]:
    return TEXT[language]

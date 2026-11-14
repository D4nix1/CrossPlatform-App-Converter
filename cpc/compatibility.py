from __future__ import annotations

from cpc.models import CompatibilityReport, FeatureComparison, PackageAnalysis

FEATURE_LABELS = {
    "camera": "Câmera",
    "location": "Localização",
    "notifications": "Notificações push",
    "bluetooth": "Bluetooth",
    "contacts": "Contatos",
    "health": "Saúde",
    "payments": "Pagamentos / compras no app",
    "biometrics": "Biometria",
    "background": "Execução em segundo plano",
}


def _feature_map(analysis: PackageAnalysis) -> dict[str, list[str]]:
    return {feature.feature_id: feature.evidence for feature in analysis.features}


def _frameworks(analysis: PackageAnalysis) -> set[str]:
    return {item.name.casefold().removesuffix(".framework") for item in analysis.dependencies if item.category == "framework"}


def compare_packages(android: PackageAnalysis, ios: PackageAnalysis) -> CompatibilityReport:
    if android.kind != "apk" or ios.kind != "ipa":
        raise ValueError("A comparação exige um APK Android e um IPA iOS.")
    android_features = _feature_map(android)
    ios_features = _feature_map(ios)
    rows: list[FeatureComparison] = []
    score = 8
    for feature_id in sorted(set(android_features) | set(ios_features)):
        left = android_features.get(feature_id, [])
        right = ios_features.get(feature_id, [])
        if left and right:
            note = "Há evidência nos dois pacotes; a implementação ainda precisa ser validada funcionalmente."
        elif left:
            note = "Detectado no APK; não foi encontrada evidência equivalente no IPA analisado."
            score += 7
        else:
            note = "Detectado no IPA; não foi encontrada evidência equivalente no APK analisado."
            score += 7
        rows.append(FeatureComparison(feature_id, FEATURE_LABELS.get(feature_id, feature_id), left, right, note))

    if android.native_binaries:
        score += 18
    if ios.native_binaries:
        score += 18
    android_frameworks, ios_frameworks = _frameworks(android), _frameworks(ios)
    score += min(20, 4 * len(android_frameworks.symmetric_difference(ios_frameworks)))
    if len(android.components) + len(ios.components) > 12:
        score += 8
    score = min(score, 100)
    difficulty = "Baixa" if score <= 25 else "Média" if score <= 55 else "Alta"

    notes: list[str] = []
    common_candidates = sorted({item.rsplit("/", 1)[-1].lower() for item in android.resource_candidates} &
                               {item.rsplit("/", 1)[-1].lower() for item in ios.resource_candidates})
    if common_candidates:
        notes.append(f"{len(common_candidates)} nome(s) de recurso aparecem nos dois pacotes; isso é apenas uma pista, não prova de equivalência.")
    else:
        notes.append("Recursos visuais, áudio, fontes e textos podem ser candidatos à reutilização após revisão de licença e conteúdo.")
    notes.append("Código compilado, bibliotecas nativas e UI específicas de uma plataforma precisam ser reimplementados ou substituídos por equivalentes.")
    if android_frameworks or ios_frameworks:
        notes.append("Frameworks identificados: " + ", ".join(sorted(android_frameworks | ios_frameworks)) + ". Confira se o mesmo framework existe e é compatível nas duas plataformas.")
    caveats = [
        "A pontuação é uma heurística baseada somente nos metadados e nomes de arquivos visíveis nos pacotes; não é uma estimativa de prazo ou custo.",
        "Ausência de evidência no pacote não prova que o app não oferece a função.",
        "O analisador não descompila código, executa o app, verifica equivalência visual/comportamental, licença ou segurança.",
        "Este relatório não converte APK em IPA nem IPA em APK.",
    ]
    return CompatibilityReport(
        android_package=android.package_id or android.file_name,
        ios_package=ios.package_id or ios.file_name,
        difficulty=difficulty,
        score=score,
        summary=f"Dificuldade estimada: {difficulty} ({score}/100), com base em evidências estáticas limitadas.",
        feature_comparisons=rows,
        portability_notes=notes,
        caveats=caveats,
    )

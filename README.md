CrossPlatform App Converter

Version: 0.15.0 Experimental · Distribution: Windows x64 installer · Dependencies: Python 3.11+ to run from source; the installed application includes portable JADX and a JRE for APK recovery.

Disclaimer: This project is not a magic solution. Analysis results and generated starter projects may contain errors or bugs, omit parts of the original application, or even result in an application that does not work. Arbitrary APKs and IPAs are not automatically converted into equivalent functional applications. Review, build, and test all generated output on the target platform before publishing or distributing it.

An experimental static analysis tool for APK and IPA packages, featuring structural compatibility estimates and assistance with cross-platform reconstruction.

The installer installs the converter itself under Program Files; it does not transform analyzed applications into APK or IPA files. Reconstruction attempts currently generate experimental ZIP archives containing starter projects, evidence, tasks, and candidate resources. The original application’s code and interface are not converted into a functional application.

License

This repository does not yet include a license for the project’s own source code. Notices and licenses for third-party components are described in THIRD_PARTY_NOTICES.md.

Windows may display an administrator permission prompt when installing under Program Files. The setup wizard displays the limitations notice, installation destination, and a list of files and folders before installation, as well as file names during installation progress.

The installer creates a Start Menu shortcut and a Windows uninstall entry. It is currently unsigned, so Windows may display an unknown publisher warning.

Getting Started

To install on Windows, run CrossPlatformAppConverter-0.15.0-Windows-Setup.exe and follow the setup wizard.

To uninstall, use Installed Apps or Add or Remove Programs in Windows.

The interface detects whether Windows is set to Portuguese. For other system languages, English is used. The installer itself offers Brazilian Portuguese and English.

The application follows the light or dark appearance configured in Windows and detects theme changes while running.

Running from source

GUI:

python run_gui.py

Command-line analysis:

python run_cli.py path\to\app.apk path\to\app.ipa --reports .\reports

Reconstruction attempt and starter project:

python run_cli.py path\to\app.apk --attempt-conversion --attempt-dir .\attempts

Approximate APK code recovery:

python run_cli.py path\to\app.apk --recover-apk --recover-dir .\recovered

APK recovery also generates:

* swiftui-layout-preview.swift: a navigable catalog in the Xcode starter project.
* android-layout-source-map.json: static references to R.layout in recovered Java code.
* A map of recovered Android images copied into the iOS asset catalog.

Run the tests:

python -m unittest discover -s tests -v

If only one package is provided, the program analyzes its structure. If both an APK and an IPA are provided, it also compares functionality indicators.

Packages are read directly and are not extracted as part of the initial analysis.

Architecture

run_gui.py / run_cli.py
          |
       cpc.analyze ───── cpc.reports
          |
   ┌──────┴──────┐
 analyzers    compatibility
   ├─ android.py  └─ evidence-based comparison
   └─ ios.py
          |
    portability.py ── starter project + native resources + plan
    recovery.py ───── portable JADX: approximate Java and Android resources

Main modules

* cpc/analyzers/android.py: identifies textual or binary Android XML manifests (AXML), permissions, SDK information, components, native libraries, and framework markers.
* cpc/analyzers/ios.py: reads Info.plist, frameworks, extensions, privacy descriptions, and IPA metadata.
* cpc/compatibility.py: compares functionality evidence between an APK and an IPA.
* cpc/reports.py: generates screen summaries and HTML/JSON reports with unique filenames.
* cpc/portability.py: generates starter projects, structured evidence inventories, and reconstruction task lists. ZIP archives also include a limited selection of candidate resources and never modify the original package.
* cpc/recovery.py: invokes the bundled portable JADX tool for APKs only. It stores approximate Java code, decoded resources, layout/menu/string inventories, and an experimental SwiftUI visual reference in a new directory, without installing or executing the analyzed package.
* run_gui.py: Tkinter graphical interface.
* run_cli.py: command-line interface.

Feature Status

Status	Available functionality
Implemented	APK/IPA detection; textual or compiled Android manifest reading; Info.plist reading; ZIP inventory; permission, component, library, and framework indicators; Android/iOS comparison; HTML/JSON reports; GUI and CLI; synthetic tests.
Experimental	Heuristic difficulty scoring; Android/SwiftUI skeleton generation; JSON/Markdown reconstruction plans; importing compatible images into native resources; approximate Java/resource recovery from APKs using JADX 1.5.6; Xcode starter project with a navigable catalog of up to 100 XML layouts, Java R.layout reference mapping, and selected raster images in Assets.xcassets. No automatic association between images and screens. The preview uses placeholders for dynamic widgets, contains no actions or application logic, and has not been compiled. The decompiler may report errors and produce incomplete code. Java is not converted to Swift.
Planned	More compatibility rules; dependency fingerprinting; optional JADX/apktool report importing; selective resource extraction into a new directory; dynamic emulator testing; equivalent-behavior validation.

Limitations and Security

* APK and IPA packages contain compiled code, not the original source project. Java recovery is partial, Android-only, and error-prone. It does not faithfully recover Kotlin, original names, comments, project structure, or native code.
* The bundled JADX tool does not execute or install APKs, but it does process their contents as input. Unsafe, non-canonical, or Windows-colliding paths are omitted before processing and listed in the report. Recovery may use up to 2 GB of memory and take several minutes. Output is written to a new directory and includes error reports and processing counts.
* Reconstruction ZIP archives contain only initial materials. Resources are selected based on file extensions and names; they are not converted or validated and may not be useful. ZIP archives are not installable APKs or IPAs and do not guarantee a working application.
* The SwiftUI reference represents only selected XML controls in a preview. It may not compile in every project and does not reflect themes, dimensions, navigation, state, interactions, or runtime-generated screens. Consult swiftui-preview-report.json and review every component.
* android-layout-source-map.json is based on textual searches in approximate recovered Java code. An R.layout reference may originate from an adapter, dialog, or code that is never executed. The map does not infer the initial screen or navigation flow.
* native-resource-map.json lists decoded images copied for review and into Assets.xcassets. Names and densities are not interpreted semantically. No image is automatically linked to a view or visually validated.
* Android manifests containing textual XML with DTDs or entities are rejected. Candidate copying filters unsafe paths and oversized files, but this is not a complete audit of compressed file formats.
* Resource and library name inventories do not necessarily identify the purpose of each resource or library. The absence of a marker does not prove that a feature is absent.
* Compatibility scores are heuristic estimates. They are not timelines, cost estimates, security audits, or guarantees of compatibility.
* The analyzer does not execute packages or verify visual behavior, licenses, signatures, integrity, or vulnerabilities.
* Android .so libraries and iOS Mach-O binaries cannot be directly reused across platforms.
* The Android starter project requires a JDK and Android SDK to build. The iOS starter project requires macOS and Xcode. This Windows machine cannot sign or compile the iOS application.
* An IPA may contain a signed provisioning profile. The current version only inventories it; it does not decode CMS signatures or entitlements.
* Reports may contain local file paths and application metadata. Store them appropriately.

File Preservation

Analysis does not extract or modify the selected APK/IPA.

Reports and starter projects are written to new files or directories. If a name already exists, a numeric suffix is added. No source file is overwritten.

See VALIDATION.md for the public packages used during validation, their hashes, and the recorded results. Test downloads are not included with the application.

Building the Windows Installer

build_windows.ps1 creates a local virtual environment under work/build-env, installs PyInstaller into it, and downloads portable JADX 1.5.6 (approximately 99 MB, including its Java runtime).

The script verifies the official SHA-256 checksum before extracting and bundling JADX with the executable.

The resulting distribution is larger, but the target computer does not need to install Python, Java, or JADX separately.

Run:

powershell -ExecutionPolicy Bypass -File .\build_installer.ps1

The script builds the application and generates a single installer using NSIS 3.13, downloaded into work/ and verified using SHA-256 before use.

The final installer is placed in:

work/installer-release/

The first build requires an internet connection to download PyInstaller, JADX, and NSIS. User installation requires administrator permission because the application is installed under Program Files.

⸻

CrossPlatform App Converter 0.15.0 — Experimental software.

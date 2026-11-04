; Installer for PDF to Excel Bot. build_exe.bat compiles it with Inno Setup 6 (ISCC) into
; dist\PDF-to-Excel-Bot-Setup-<version>.exe, passing the version from pdf_excel_bot\__init__.py.
;
; Installs for the current user only (no admin rights or IT ticket needed), adds Start menu and
; desktop shortcuts and an Apps & Features uninstaller, and installs Microsoft's WebView2 runtime
; when the PC doesn't have it (the window needs it). Running a newer Setup upgrades in place.

#define MyAppName "PDF to Excel Bot"
#define MyAppExeName "PDF to Excel Bot.exe"
#ifndef MyAppVersion
  #define MyAppVersion "0.0"
#endif

[Setup]
; Never change AppId: it's how a newer Setup finds and upgrades an existing install.
AppId={{79ED56CA-B3BB-4B19-ACFF-A4F55A1E6992}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
VersionInfoVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
; Close the bot if it's open when upgrading or uninstalling.
CloseApplications=yes
OutputDir=..\dist
OutputBaseFilename=PDF-to-Excel-Bot-Setup-{#MyAppVersion}
SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; An upgrade replaces the app's libraries wholesale, so no stale files from an older version linger.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\{#MyAppName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "redist\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: NeedsWebView2

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Run without admin rights, Microsoft's bootstrapper installs WebView2 for this user. It downloads
; about 100 MB; if it can't (offline), the bot still works and opens its classic window instead.
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; \
  StatusMsg: "Installing Microsoft WebView2 (the window needs it)..."; Check: NeedsWebView2; Flags: waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
const
  WebView2Key = 'Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function HasWebView2(RootKey: Integer; SubKey: String): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(RootKey, SubKey, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0');
end;

{ Where Microsoft says to look: machine-wide (32-bit registry view) or for this user. }
function NeedsWebView2: Boolean;
begin
  Result := not (HasWebView2(HKLM32, 'SOFTWARE\' + WebView2Key)
    or HasWebView2(HKLM64, 'SOFTWARE\' + WebView2Key)
    or HasWebView2(HKCU, 'Software\' + WebView2Key));
end;

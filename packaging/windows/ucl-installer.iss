; Build from repository root: ISCC /DAppVersion=0.3.0 packaging\windows\ucl-installer.iss
#ifndef AppVersion
  #define AppVersion "0.3.0"
#endif
#ifndef OutputBase
  #define OutputBase "ucl-installer"
#endif

[Setup]
AppId={{0C8AB115-0E06-48F6-AC2D-0142CC6EE055}
AppName=Universal Coding Language
AppVersion={#AppVersion}
AppPublisher=UCL contributors
AppPublisherURL=https://github.com/Arvex-GH/universal-coding
DefaultDirName={localappdata}\Programs\UCL
DefaultGroupName=UCL
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist
OutputBaseFilename={#OutputBase}
LicenseFile=..\..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ChangesEnvironment=yes
ChangesAssociations=yes
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={app}\ucl.exe
VersionInfoVersion={#AppVersion}

[Tasks]
Name: addtopath; Description: "Add UCL to my terminal PATH (recommended)"; Flags: checkedonce
Name: editor; Description: "Add .ucl file actions to Windows Explorer"; Flags: checkedonce

[Files]
Source: "..\..\dist\ucl\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\examples\*.ucl"; DestDir: "{app}\examples"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\docs\windows.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\UCL command prompt"; Filename: "{cmd}"; Parameters: "/K """"{app}\ucl.exe"" --version"""; WorkingDir: "{app}\examples"
Name: "{group}\UCL documentation"; Filename: "https://github.com/Arvex-GH/universal-coding/tree/main/docs"
Name: "{group}\UCL examples"; Filename: "{app}\examples"
Name: "{group}\Uninstall UCL"; Filename: "{uninstallexe}"

[Registry]
; Do not replace the user's default editor. Register Open With and a separate Run action.
Root: HKCU; Subkey: "Software\Classes\.ucl\OpenWithProgids"; ValueType: string; ValueName: "UCL.Source"; ValueData: ""; Flags: uninsdeletevalue; Tasks: editor
Root: HKCU; Subkey: "Software\Classes\UCL.Source"; ValueType: string; ValueData: "UCL source file"; Flags: uninsdeletekey; Tasks: editor
Root: HKCU; Subkey: "Software\Classes\UCL.Source\shell\open\command"; ValueType: string; ValueData: """{sys}\notepad.exe"" ""%1"""; Tasks: editor
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.ucl\shell\UCLRun"; ValueType: string; ValueData: "Run with UCL"; Flags: uninsdeletekey; Tasks: editor
Root: HKCU; Subkey: "Software\Classes\SystemFileAssociations\.ucl\shell\UCLRun\command"; ValueType: string; ValueData: """{cmd}"" /D /K """"{app}\ucl.exe"" run ""%1"""""; Tasks: editor

[Code]
const
  OwnerKey = 'Software\UCL\Installer';

function SameEntry(A, B: String): Boolean;
begin
  StringChangeEx(A, '"', '', True);
  StringChangeEx(B, '"', '', True);
  Result := CompareText(RemoveBackslashUnlessRoot(Trim(A)), RemoveBackslashUnlessRoot(Trim(B))) = 0;
end;

function WithoutEntry(Path, Entry: String): String;
var
  P: Integer;
  Part: String;
begin
  Result := '';
  while Path <> '' do begin
    P := Pos(';', Path);
    if P = 0 then P := Length(Path) + 1;
    Part := Copy(Path, 1, P - 1);
    Delete(Path, 1, P);
    if not SameEntry(Part, Entry) then begin
      if Result <> '' then Result := Result + ';';
      Result := Result + Part;
    end;
  end;
end;

function HasEntry(Path, Entry: String): Boolean;
var
  P: Integer;
  Part: String;
begin
  Result := False;
  while Path <> '' do begin
    P := Pos(';', Path);
    if P = 0 then P := Length(Path) + 1;
    Part := Copy(Path, 1, P - 1);
    Delete(Path, 1, P);
    if SameEntry(Part, Entry) then begin
      Result := True;
      Exit;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Path, Owned, AppDir: String;
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('addtopath') then begin
    RegQueryStringValue(HKCU, 'Environment', 'Path', Path);
    RegQueryStringValue(HKCU, OwnerKey, 'PathEntry', Owned);
    AppDir := ExpandConstant('{app}');
    if (Owned <> '') and not SameEntry(Owned, AppDir) then begin
      Path := WithoutEntry(Path, Owned);
      if not RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Path) then
        RaiseException('Could not update the previous UCL PATH entry.');
      RegDeleteValue(HKCU, OwnerKey, 'PathEntry');
    end;
    if not HasEntry(Path, AppDir) then begin
      if (Path <> '') and (Copy(Path, Length(Path), 1) <> ';') then Path := Path + ';';
      Path := Path + AppDir;
      if not RegWriteExpandStringValue(HKCU, 'Environment', 'Path', Path) then
        RaiseException('Could not add UCL to your user PATH.');
      RegWriteStringValue(HKCU, OwnerKey, 'PathEntry', AppDir);
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Path, Owned: String;
begin
  if CurUninstallStep = usPostUninstall then begin
    RegQueryStringValue(HKCU, OwnerKey, 'PathEntry', Owned);
    if Owned <> '' then begin
      RegQueryStringValue(HKCU, 'Environment', 'Path', Path);
      RegWriteExpandStringValue(HKCU, 'Environment', 'Path', WithoutEntry(Path, Owned));
      RegDeleteValue(HKCU, OwnerKey, 'PathEntry');
      RegDeleteKeyIfEmpty(HKCU, OwnerKey);
    end;
  end;
end;

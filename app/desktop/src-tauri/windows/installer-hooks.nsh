; Página "Pasta de arquivos" do instalador do Monitor.
; Este arquivo precisa ficar em UTF-8 com BOM para o NSIS ler os acentos.
!include nsDialogs.nsh
!include LogicLib.nsh
!include FileFunc.nsh

Var MonitorFilesDir
Var MonitorFilesInput

Function MonitorFilesPage
  ; Instalação passiva ou atualização: mantém a pasta já configurada.
  ClearErrors
  ${GetOptions} $CMDLINE "/P" $0
  ${IfNot} ${Errors}
    Abort
  ${EndIf}
  ClearErrors
  ${GetOptions} $CMDLINE "/UPDATE" $0
  ${IfNot} ${Errors}
    Abort
  ${EndIf}
  ClearErrors

  ${If} $MonitorFilesDir == ""
    ReadRegStr $MonitorFilesDir HKCU "Software\Monitor" "FilesDir"
  ${EndIf}
  ${If} $MonitorFilesDir == ""
    ReadEnvStr $0 "OneDrive"
    ${If} $0 != ""
      StrCpy $MonitorFilesDir "$0\Monitor"
    ${Else}
      StrCpy $MonitorFilesDir "$DOCUMENTS\Monitor"
    ${EndIf}
  ${EndIf}

  !insertmacro MUI_HEADER_TEXT "Pasta de arquivos" "Onde o Monitor salva backups, exportações e arquivos organizados."
  nsDialogs::Create 1018
  Pop $0
  ${If} $0 == error
    Abort
  ${EndIf}
  ${NSD_CreateLabel} 0 0 100% 34u "Escolha a pasta onde o Monitor vai guardar os arquivos que criar ou organizar. Para manter tudo na nuvem, selecione uma pasta dentro do OneDrive."
  Pop $0
  ${NSD_CreateLabel} 0 42u 100% 10u "Pasta de arquivos:"
  Pop $0
  ${NSD_CreateDirRequest} 0 54u 75% 13u "$MonitorFilesDir"
  Pop $MonitorFilesInput
  ${NSD_CreateBrowseButton} 77% 53u 23% 15u "Procurar..."
  Pop $0
  ${NSD_OnClick} $0 MonitorFilesBrowse
  ${NSD_CreateLabel} 0 78u 100% 44u "O banco de dados em uso continua neste computador, porque sincronizá-lo aberto pode corrompê-lo; uma cópia diária vai para esta pasta. Você pode trocar a pasta depois em Configurações. Desinstalar o Monitor não apaga esta pasta."
  Pop $0
  nsDialogs::Show
FunctionEnd

Function MonitorFilesBrowse
  ${NSD_GetText} $MonitorFilesInput $0
  nsDialogs::SelectFolderDialog "Escolha a pasta de arquivos do Monitor" "$0"
  Pop $1
  ${If} $1 != error
    ${NSD_SetText} $MonitorFilesInput "$1"
  ${EndIf}
FunctionEnd

Function MonitorFilesPageLeave
  ${NSD_GetText} $MonitorFilesInput $MonitorFilesDir
  ${If} $MonitorFilesDir == ""
    MessageBox MB_ICONEXCLAMATION "Escolha a pasta onde o Monitor vai salvar seus arquivos."
    Abort
  ${EndIf}
FunctionEnd

!macro NSIS_HOOK_PREINSTALL
  ; O backend roda como processo separado e manteria o executável aberto durante a atualização.
  nsExec::Exec 'taskkill /F /IM monitor-backend.exe'
  Pop $0
  Sleep 500
!macroend

!macro NSIS_HOOK_POSTINSTALL
  ; Grava a escolha para o aplicativo ler na primeira execução.
  ${If} $MonitorFilesDir != ""
    CreateDirectory "$MonitorFilesDir"
    WriteRegStr HKCU "Software\Monitor" "FilesDir" "$MonitorFilesDir"
  ${EndIf}
!macroend

; Transkrib SmartCut AI - Custom NSIS installer page
; Страница согласия с документами

!include "MUI2.nsh"
!include "nsDialogs.nsh"
!include "LogicLib.nsh"

Var Dialog
Var CheckEULA
Var CheckPrivacy
Var EULALink
Var PrivacyLink
Var EULAChecked
Var PrivacyChecked

; Кастомная страница согласия
Page custom AgreementPage AgreementPageLeave

Function AgreementPage
  nsDialogs::Create 1018
  Pop $Dialog
  ${If} $Dialog == error
    Abort
  ${EndIf}

  ; Заголовок
  ${NSD_CreateLabel} 0 0 100% 20u "Пожалуйста, ознакомьтесь с документами и подтвердите своё согласие:"
  Pop $0
  SetCtlColors $0 "" transparent

  ; Разделитель
  ${NSD_CreateHLine} 0 22u 100% 1u ""
  Pop $0

  ; Ссылка на EULA
  ${NSD_CreateLink} 0 30u 100% 12u "Лицензионное соглашение (EULA)"
  Pop $EULALink
  ${NSD_OnClick} $EULALink OpenEULA

  ; Чекбокс EULA
  ${NSD_CreateCheckbox} 0 45u 100% 12u "Я прочитал(а) и принимаю условия Лицензионного соглашения"
  Pop $CheckEULA

  ; Ссылка на Политику конфиденциальности
  ${NSD_CreateLink} 0 62u 100% 12u "Политика конфиденциальности"
  Pop $PrivacyLink
  ${NSD_OnClick} $PrivacyLink OpenPrivacy

  ; Чекбокс Privacy Policy
  ${NSD_CreateCheckbox} 0 77u 100% 12u "Я прочитал(а) и принимаю Политику конфиденциальности"
  Pop $CheckPrivacy

  ; Подсказка
  ${NSD_CreateLabel} 0 95u 100% 20u "Установка невозможна без принятия обоих документов."
  Pop $0
  SetCtlColors $0 808080 transparent

  nsDialogs::Show
FunctionEnd

; Открыть EULA в блокноте
Function OpenEULA
  ExecShell "open" "$INSTDIR\docs\EULA_RU.txt"
  ; Если ещё не установлено - открыть из temp
  IfErrors 0 +2
  ExecShell "open" "$EXEDIR\docs\EULA_RU.txt"
FunctionEnd

; Открыть Политику конфиденциальности
Function OpenPrivacy
  ExecShell "open" "$INSTDIR\docs\PRIVACY_POLICY_RU.txt"
  IfErrors 0 +2
  ExecShell "open" "$EXEDIR\docs\PRIVACY_POLICY_RU.txt"
FunctionEnd

; Проверка чекбоксов перед продолжением
Function AgreementPageLeave
  ${NSD_GetState} $CheckEULA $EULAChecked
  ${NSD_GetState} $CheckPrivacy $PrivacyChecked

  ${If} $EULAChecked != ${BST_CHECKED}
    MessageBox MB_OK|MB_ICONEXCLAMATION "Необходимо принять Лицензионное соглашение для продолжения установки."
    Abort
  ${EndIf}

  ${If} $PrivacyChecked != ${BST_CHECKED}
    MessageBox MB_OK|MB_ICONEXCLAMATION "Необходимо принять Политику конфиденциальности для продолжения установки."
    Abort
  ${EndIf}
FunctionEnd

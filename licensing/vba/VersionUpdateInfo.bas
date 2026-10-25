Attribute VB_Name = "VersionUpdateInfo"
Option Explicit

' Import this standard module in the ERP workbook.
' Put only this in ThisWorkbook:
' Private Sub Workbook_Open()
'     CheckErpVersionOnOpen
' End Sub

Private Const ERP_VERSION_API_URL As String = "https://webautomationexcel.com/api/licensing/erp/version/"
Private Const USER_SHEET_NAME As String = "User"
Private Const VERSION_CELL As String = "B6"
Private Const VERSION_INFO_ID As Long = 3
Private Const HTTP_TIMEOUT_MS As Long = 30000
Private Const PROMPT_TITLE As String = "@DilipDelwash"




#If VBA7 Then
    Private Declare PtrSafe Function SetWindowsHookEx Lib "user32" _
        Alias "SetWindowsHookExA" ( _
        ByVal idHook As Long, _
        ByVal lpfn As LongPtr, _
        ByVal hMod As LongPtr, _
        ByVal dwThreadId As Long) As LongPtr

    Private Declare PtrSafe Function UnhookWindowsHookEx Lib "user32" ( _
        ByVal hHook As LongPtr) As Long

    Private Declare PtrSafe Function GetCurrentThreadId Lib "kernel32" () As Long

    Private Declare PtrSafe Function SetWindowPos Lib "user32" ( _
        ByVal hWnd As LongPtr, _
        ByVal hWndInsertAfter As LongPtr, _
        ByVal X As Long, _
        ByVal Y As Long, _
        ByVal cx As Long, _
        ByVal cy As Long, _
        ByVal uFlags As Long) As Long

    Private Declare PtrSafe Function GetWindowRect Lib "user32" ( _
        ByVal hWnd As LongPtr, lpRect As RECT) As Long

    Private Declare PtrSafe Function GetSystemMetrics Lib "user32" ( _
        ByVal nIndex As Long) As Long

    Private hHook As LongPtr
#Else
    Private Declare Function SetWindowsHookEx Lib "user32" _
        Alias "SetWindowsHookExA" ( _
        ByVal idHook As Long, _
        ByVal lpfn As Long, _
        ByVal hMod As Long, _
        ByVal dwThreadId As Long) As Long

    Private Declare Function UnhookWindowsHookEx Lib "user32" ( _
        ByVal hHook As Long) As Long

    Private Declare Function GetCurrentThreadId Lib "kernel32" () As Long

    Private Declare Function SetWindowPos Lib "user32" ( _
        ByVal hWnd As Long, _
        ByVal hWndInsertAfter As Long, _
        ByVal X As Long, _
        ByVal Y As Long, _
        ByVal cx As Long, _
        ByVal cy As Long, _
        ByVal uFlags As Long) As Long

    Private Declare Function GetWindowRect Lib "user32" ( _
        ByVal hWnd As Long, lpRect As RECT) As Long

    Private Declare Function GetSystemMetrics Lib "user32" ( _
        ByVal nIndex As Long) As Long

    Private hHook As Long
#End If

Private Type RECT
    Left As Long
    Top As Long
    Right As Long
    Bottom As Long
End Type

Private Const WH_CBT As Long = 5
Private Const HCBT_ACTIVATE As Long = 5
Private Const SWP_NOSIZE As Long = &H1
Private Const SWP_NOZORDER As Long = &H4

Private MsgTop As Long

#If VBA7 Then
Private Function MsgBoxHook(ByVal nCode As Long, _
                            ByVal wParam As LongPtr, _
                            ByVal lParam As LongPtr) As LongPtr
#Else
Private Function MsgBoxHook(ByVal nCode As Long, _
                            ByVal wParam As Long, _
                            ByVal lParam As Long) As Long
#End If

    If nCode = HCBT_ACTIVATE Then

        Dim r As RECT
        Dim X As Long

        If GetWindowRect(wParam, r) <> 0 Then
            X = (GetSystemMetrics(0) - (r.Right - r.Left)) \ 2

            SetWindowPos wParam, 0, X, MsgTop, 0, 0, _
                         SWP_NOSIZE Or SWP_NOZORDER
        End If

        If hHook <> 0 Then
            UnhookWindowsHookEx hHook
            hHook = 0
        End If

    End If

End Function

Public Function MsgBoxAt( _
    ByVal Prompt As String, _
    ByVal TopPosition As Long, _
    Optional ByVal Buttons As VbMsgBoxStyle = vbOKOnly, _
    Optional ByVal Title As String = "") As VbMsgBoxResult

    MsgTop = TopPosition

    hHook = SetWindowsHookEx(WH_CBT, AddressOf MsgBoxHook, _
                            0, GetCurrentThreadId())

    MsgBoxAt = MsgBox(Prompt, Buttons, Title)

    If hHook <> 0 Then
        UnhookWindowsHookEx hHook
        hHook = 0
    End If

End Function



Public Sub CheckErpVersionOnOpen()
    Dim currentVersion As String
    Dim responseText As String
    Dim latestVersion As String
    Dim downloadUrl As String

    On Error GoTo VersionCheckError

    currentVersion = Trim$(CStr(ThisWorkbook.Worksheets(USER_SHEET_NAME).Range(VERSION_CELL).Value2))
    If Len(currentVersion) = 0 Then Exit Sub

    responseText = GetErpVersionResponse(currentVersion)
    If Not JsonBooleanValue(responseText, "success") Then Exit Sub
    If Not JsonBooleanValue(responseText, "update_available") Then Exit Sub

    latestVersion = JsonStringValue(responseText, "latest_version")
    downloadUrl = JsonStringValue(responseText, "download_url")
    If Len(downloadUrl) = 0 Then
        MsgBox "New ERP version " & latestVersion & " available hai." & vbCrLf & _
               "Update link abhi server par configure nahi hai.", vbExclamation, PROMPT_TITLE
    ElseIf MsgBox("New ERP version " & latestVersion & " available hai." & vbCrLf & vbCrLf & _
                  "Google Drive update folder kholna chahte hain?", vbQuestion + vbYesNo, PROMPT_TITLE) = vbYes Then
        ThisWorkbook.FollowHyperlink downloadUrl
    End If
    Exit Sub

VersionCheckError:
    ' Workbook open ko version-service/network failure se stop nahi karna hai.
End Sub

Private Function GetErpVersionResponse(ByVal currentVersion As String) As String
    Dim http As Object
    Set http = CreateObject("WinHttp.WinHttpRequest.5.1")
    http.SetTimeouts HTTP_TIMEOUT_MS, HTTP_TIMEOUT_MS, HTTP_TIMEOUT_MS, HTTP_TIMEOUT_MS
    http.Open "POST", ERP_VERSION_API_URL, False
    http.SetRequestHeader "Content-Type", "application/json"
    http.SetRequestHeader "Accept", "application/json"
    http.Send "{""id"":" & CStr(VERSION_INFO_ID) & ",""current_version"":""" & JsonEscapeValue(currentVersion) & """}"
    If CLng(http.Status) >= 200 And CLng(http.Status) < 300 Then GetErpVersionResponse = CStr(http.responseText)
End Function

Private Function JsonEscapeValue(ByVal value As String) As String
    value = Replace(value, "\", "\\")
    JsonEscapeValue = Replace(value, Chr$(34), "\" & Chr$(34))
End Function

Private Function JsonBooleanValue(ByVal json As String, ByVal key As String) As Boolean
    JsonBooleanValue = (LCase$(JsonRawValue(json, key)) = "true")
End Function

Private Function JsonStringValue(ByVal json As String, ByVal key As String) As String
    Dim raw As String
    raw = JsonRawValue(json, key)
    If Left$(raw, 1) = Chr$(34) And Right$(raw, 1) = Chr$(34) Then
        JsonStringValue = Replace(Mid$(raw, 2, Len(raw) - 2), "\" & Chr$(34), Chr$(34))
    End If
End Function

Private Function JsonRawValue(ByVal json As String, ByVal key As String) As String
    Dim position As Long, startAt As Long, endAt As Long
    position = InStr(1, json, Chr$(34) & key & Chr$(34), vbTextCompare)
    If position = 0 Then Exit Function
    startAt = InStr(position, json, ":") + 1
    Do While startAt <= Len(json) And InStr(" " & vbTab & vbCr & vbLf, Mid$(json, startAt, 1)) > 0
        startAt = startAt + 1
    Loop
    If Mid$(json, startAt, 1) = Chr$(34) Then
        endAt = InStr(startAt + 1, json, Chr$(34))
        If endAt > startAt Then JsonRawValue = Mid$(json, startAt, endAt - startAt + 1)
    Else
        endAt = InStr(startAt, json & ",", ",")
        JsonRawValue = Trim$(Mid$(json, startAt, endAt - startAt))
    End If
End Function

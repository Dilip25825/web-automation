Attribute VB_Name = "ErpApiLogin"
Option Explicit

' True = localhost testing, False = Render production.
Private Const USE_LOCAL_SERVER As Boolean = True
Private Const LOCAL_BASE_URL As String = "http://127.0.0.1:8000"
Private Const PRODUCTION_BASE_URL As String = "https://web-automation-maar.onrender.com"
Private Const TOKEN_SETTINGS_APP As String = "WebAutomationWithExcel"
Private Const TOKEN_SETTINGS_SECTION As String = "ErpDeviceTokens"
Private Const USER_SHEET As String = "User"
Private Const OPERATOR_MOBILE_CELL As String = "B1"
Private Const ERP_PASSWORD_CELL As String = "B2"
Private Const RECORD_ID_CELL As String = "B4"
Private Const PACS_NAME_CELL As String = "D2"
Private Const REGISTRATION_DATE_CELL As String = "D3"
Private Const EXPIRY_DATE_CELL As String = "D4"
Private Const HTTP_TIMEOUT_MS As Long = 30000
Private Const API_PROMPT_TITLE As String = "@DilipDelwash"

Public Type ErpApiSubscriptionInfo
    RecordID As Long
    ErpUserID As String
    PacsName As String
    OperatorMobile As String
    Status As String
    StatusMessage As String
    RegistrationUrl As String
    PaymentCreateUrl As String
    RegistrationDate As Date
    ExpiryDate As Date
    ServerDate As Date
End Type

Public currentVersion As String
Public newVersion As String

Public Sub CheckVersion()
    Dim operatorMobile As String
    Dim responseText As String
    Dim statusValue As String
    Dim errorMessage As String

    On Error GoTo VersionError

    If Not TryGetOperatorMobile(operatorMobile) Then
        MsgBox "User sheet ke B1 me valid 10 digit Operator Mobile dalein.", vbExclamation, API_PROMPT_TITLE
        Exit Sub
    End If

    currentVersion = Trim$(CStr(ThisWorkbook.Worksheets(USER_SHEET).Range("B6").Value2))
    If Len(currentVersion) = 0 Then
        MsgBox "User sheet ke B6 me current version nahi hai.", vbExclamation, API_PROMPT_TITLE
        Exit Sub
    End If

    If Not SendVersionRequest(operatorMobile, currentVersion, responseText, errorMessage) Then
        MsgBox errorMessage, vbExclamation, API_PROMPT_TITLE
        Exit Sub
    End If

    statusValue = UCase$(JsonString(responseText, "status"))
    newVersion = JsonString(responseText, "latest_version")

    If JsonBoolean(responseText, "update_available", False) Then
        frmUpdate.Show
    Else
        MsgBox "No new version available." & vbCrLf & "You are already using version " & currentVersion & ".", vbInformation, "Updated"
    End If
    Exit Sub

VersionError:
    MsgBox "Version check complete nahi ho saka." & vbCrLf & err.Description, vbExclamation, API_PROMPT_TITLE
End Sub

Private Function SendVersionRequest(ByVal operatorMobile As String, ByVal currentVersion As String, ByRef responseText As String, ByRef errorMessage As String) As Boolean
    Dim http As Object
    Dim endpoint As String
    Dim requestBody As String
    Dim httpStatus As Long
    Dim apiStatus As String
    Dim apiMessage As String
    Dim clientToken As String

    On Error GoTo RequestError

    If Not EnsureErpClientToken(operatorMobile, clientToken, errorMessage) Then Exit Function

    endpoint = ApiBaseUrl() & "/api/licensing/erp/version/"
    requestBody = "{""operator_mobile"":""" & JsonEscape(operatorMobile) & """,""current_version"":""" & JsonEscape(currentVersion) & """}"

    Set http = CreateObject("WinHttp.WinHttpRequest.5.1")
    http.SetTimeouts HTTP_TIMEOUT_MS, HTTP_TIMEOUT_MS, HTTP_TIMEOUT_MS, HTTP_TIMEOUT_MS
    http.Open "POST", endpoint, False
    http.SetRequestHeader "Content-Type", "application/json"
    http.SetRequestHeader "Accept", "application/json"
    http.SetRequestHeader "Authorization", "Bearer " & clientToken
    http.Send requestBody

    httpStatus = CLng(http.Status)
    responseText = CStr(http.ResponseText)
    If httpStatus < 200 Or httpStatus >= 300 Or Not JsonBoolean(responseText, "success", False) Then
        apiStatus = JsonString(responseText, "status")
        apiMessage = JsonString(responseText, "message")
        errorMessage = "ERP version API error: HTTP " & CStr(httpStatus)
        If Len(apiStatus) > 0 Then errorMessage = errorMessage & vbCrLf & "Status: " & apiStatus
        If Len(apiMessage) > 0 Then errorMessage = errorMessage & vbCrLf & apiMessage
        Exit Function
    End If

    SendVersionRequest = True
    Exit Function

RequestError:
    errorMessage = "ERP version server se connection nahi ho saka." & vbCrLf & err.Description
End Function
Public Sub Login()
    Dim operatorMobile As String
    Dim subscription As ErpApiSubscriptionInfo
    Dim apiError As String

    On Error GoTo LoginError

    If Not TryGetOperatorMobile(operatorMobile) Then
        MsgBox "User sheet ke B1 me valid 10 digit Operator Mobile dalein.", vbExclamation, API_PROMPT_TITLE
        Exit Sub
    End If

    ' Existing pending Razorpay link ko API se reconcile karne dein.
    On Error Resume Next
    CheckPendingErpPayment
    On Error GoTo LoginError

    If Not FetchErpSubscription(operatorMobile, subscription, apiError) Then
        MsgBox apiError, vbExclamation, API_PROMPT_TITLE
        Exit Sub
    End If

    WriteSubscriptionDetails subscription

    Select Case UCase$(subscription.Status)
        Case "ACTIVE"
            ThisWorkbook.Worksheets(USER_SHEET).Range(RECORD_ID_CELL).Value2 = subscription.RecordID
            LoginToErp subscription.ErpUserID, CStr(ThisWorkbook.Worksheets(USER_SHEET).Range(ERP_PASSWORD_CELL).Value2), subscription.ServerDate

        Case "LICENSE_NOT_FOUND"
            If Len(subscription.RegistrationUrl) = 0 Then
                MsgBox "Registration URL API se nahi mili.", vbExclamation, API_PROMPT_TITLE
                Exit Sub
            End If
            If MsgBox("ERP user nahi mila." & vbCrLf & vbCrLf & "Web page par user registration kholna chahte hain?", vbQuestion + vbYesNo, API_PROMPT_TITLE) = vbYes Then
                ThisWorkbook.FollowHyperlink subscription.RegistrationUrl
            End If

        Case "PAYMENT_REQUIRED", "EXPIRED"
            If subscription.RecordID > 0 Then
                ThisWorkbook.Worksheets(USER_SHEET).Range(RECORD_ID_CELL).Value2 = subscription.RecordID
            End If
            If MsgBox(subscription.StatusMessage & vbCrLf & vbCrLf & "Payment/renewal start karna chahte hain?", vbQuestion + vbYesNo, API_PROMPT_TITLE) = vbYes Then
                StartPaymentFlow
            End If

        Case Else
            MsgBox subscription.StatusMessage, vbExclamation, API_PROMPT_TITLE
    End Select
    Exit Sub

LoginError:
    MsgBox "Login could not be completed." & vbCrLf & err.Description, vbExclamation, API_PROMPT_TITLE
End Sub

Private Sub WriteSubscriptionDetails(ByRef info As ErpApiSubscriptionInfo)
    Dim userSheet As Worksheet
    Set userSheet = ThisWorkbook.Worksheets(USER_SHEET)

    userSheet.Range(PACS_NAME_CELL).Value2 = info.PacsName

    If info.RegistrationDate > 0 Then
        userSheet.Range(REGISTRATION_DATE_CELL).Value2 = Format$(info.RegistrationDate, "dd-mm-yyyy")

    Else
        userSheet.Range(REGISTRATION_DATE_CELL).ClearContents
    End If

    If info.ExpiryDate > 0 Then
        userSheet.Range(EXPIRY_DATE_CELL).Value2 = Format$(info.ExpiryDate, "dd-mm-yyyy")

    Else
        userSheet.Range(EXPIRY_DATE_CELL).ClearContents
    End If
End Sub
Private Function TryGetOperatorMobile(ByRef operatorMobile As String) As Boolean
    Dim rawValue As Variant
    Dim digits As String

    rawValue = ThisWorkbook.Worksheets(USER_SHEET).Range(OPERATOR_MOBILE_CELL).Value2
    If IsError(rawValue) Then Exit Function

    digits = OnlyDigits(Trim$(CStr(rawValue)))
    If Len(digits) = 12 And Left$(digits, 2) = "91" Then digits = Right$(digits, 10)
    If Len(digits) <> 10 Then Exit Function
    If InStr(1, "6789", Left$(digits, 1), vbBinaryCompare) = 0 Then Exit Function

    operatorMobile = digits
    TryGetOperatorMobile = True
End Function

Private Function FetchErpSubscription(ByVal operatorMobile As String, ByRef info As ErpApiSubscriptionInfo, ByRef errorMessage As String) As Boolean
    Dim http As Object
    Dim endpoint As String
    Dim requestBody As String
    Dim responseText As String
    Dim httpStatus As Long
    Dim successValue As Boolean
    Dim clientToken As String

    On Error GoTo RequestError

    If Not EnsureErpClientToken(operatorMobile, clientToken, errorMessage) Then Exit Function

    endpoint = ApiBaseUrl() & "/api/licensing/erp/subscription/"
    requestBody = "{""operator_mobile"":""" & JsonEscape(operatorMobile) & """}"

    Set http = CreateObject("WinHttp.WinHttpRequest.5.1")
    http.SetTimeouts HTTP_TIMEOUT_MS, HTTP_TIMEOUT_MS, HTTP_TIMEOUT_MS, HTTP_TIMEOUT_MS
    http.Open "POST", endpoint, False
    http.SetRequestHeader "Content-Type", "application/json"
    http.SetRequestHeader "Accept", "application/json"
    http.SetRequestHeader "Authorization", "Bearer " & clientToken
    http.Send requestBody

    httpStatus = CLng(http.Status)
    responseText = CStr(http.ResponseText)
    successValue = JsonBoolean(responseText, "success", False)

    info.Status = JsonString(responseText, "status")
    info.StatusMessage = JsonString(responseText, "message")
    info.OperatorMobile = JsonString(responseText, "operator_mobile")
    info.RegistrationUrl = JsonString(responseText, "registration_url")
    info.PaymentCreateUrl = JsonString(responseText, "payment_create_url")
    info.ErpUserID = JsonString(responseText, "erp_id")
    info.PacsName = JsonString(responseText, "pacs_name")
    info.RecordID = JsonLong(responseText, "record_id", 0)
    info.RegistrationDate = JsonIsoDate(responseText, "registration_date")
    info.ExpiryDate = JsonIsoDate(responseText, "expiry_date")
    info.ServerDate = JsonIsoDate(responseText, "server_date")

    If httpStatus < 200 Or httpStatus >= 300 Or Not successValue Then
        errorMessage = "ERP subscription API error: HTTP " & CStr(httpStatus)
        If Len(info.Status) > 0 Then errorMessage = errorMessage & vbCrLf & "Status: " & info.Status
        If Len(info.StatusMessage) > 0 Then errorMessage = errorMessage & vbCrLf & info.StatusMessage
        Exit Function
    End If

    If Len(info.StatusMessage) = 0 Then info.StatusMessage = "ERP subscription status: " & info.Status
    FetchErpSubscription = True
    Exit Function

RequestError:
    errorMessage = "ERP subscription server se connection nahi ho saka." & vbCrLf & err.Description
End Function

Public Function getUpiID() As String
    Dim operatorMobile As String
    Dim http As Object
    Dim endpoint As String
    Dim requestBody As String
    Dim responseText As String
    Dim apiMessage As String
    Dim clientToken As String

    On Error GoTo UpiError

    If Not TryGetOperatorMobile(operatorMobile) Then
        Err.Raise vbObjectError + 2101, "getUpiID", "User sheet ke B1 me valid 10 digit Operator Mobile nahi hai."
    End If

    If Not EnsureErpClientToken(operatorMobile, clientToken, apiMessage) Then
        Err.Raise vbObjectError + 2102, "getUpiID", apiMessage
    End If

    endpoint = ApiBaseUrl() & "/api/licensing/erp/upi/"
    requestBody = "{""operator_mobile"":""" & JsonEscape(operatorMobile) & """}"

    Set http = CreateObject("WinHttp.WinHttpRequest.5.1")
    http.SetTimeouts HTTP_TIMEOUT_MS, HTTP_TIMEOUT_MS, HTTP_TIMEOUT_MS, HTTP_TIMEOUT_MS
    http.Open "POST", endpoint, False
    http.SetRequestHeader "Content-Type", "application/json"
    http.SetRequestHeader "Accept", "application/json"
    http.SetRequestHeader "Authorization", "Bearer " & clientToken
    http.Send requestBody

    responseText = CStr(http.ResponseText)
    If CLng(http.Status) < 200 Or CLng(http.Status) >= 300 Or Not JsonBoolean(responseText, "success", False) Then
        apiMessage = JsonString(responseText, "message")
        If Len(apiMessage) = 0 Then apiMessage = JsonString(responseText, "status")
        If Len(apiMessage) = 0 Then apiMessage = "HTTP " & CStr(http.Status)
        Err.Raise vbObjectError + 2103, "getUpiID", "UPI API error: " & apiMessage
    End If

    getUpiID = Trim$(JsonString(responseText, "upi_id"))
    If Len(getUpiID) = 0 Then
        Err.Raise vbObjectError + 2104, "getUpiID", "Server se active UPI ID nahi mili."
    End If
    Exit Function

UpiError:
    Err.Raise Err.Number, "getUpiID", Err.Description
End Function
Private Function EnsureErpClientToken(ByVal operatorMobile As String, ByRef clientToken As String, ByRef errorMessage As String) As Boolean
    Dim http As Object
    Dim endpoint As String
    Dim requestBody As String
    Dim responseText As String
    Dim deviceID As String
    Dim apiStatus As String
    Dim apiMessage As String
    Dim registrationUrl As String

    On Error GoTo RegistrationError

    clientToken = Trim$(GetSetting(TOKEN_SETTINGS_APP, TOKEN_SETTINGS_SECTION, operatorMobile, vbNullString))
    If Len(clientToken) >= 32 Then
        EnsureErpClientToken = True
        Exit Function
    End If

    deviceID = Trim$(Environ$("COMPUTERNAME")) & "|" & Trim$(Environ$("USERDOMAIN")) & "|" & Trim$(Environ$("USERNAME"))
    If Len(Replace(deviceID, "|", vbNullString)) < 4 Then
        errorMessage = "Windows device identity read nahi ho saki."
        Exit Function
    End If

    endpoint = ApiBaseUrl() & "/api/licensing/erp/device/register/"
    requestBody = "{""operator_mobile"":""" & JsonEscape(operatorMobile) & """,""device_id"":""" & JsonEscape(deviceID) & """}"

    Set http = CreateObject("WinHttp.WinHttpRequest.5.1")
    http.SetTimeouts HTTP_TIMEOUT_MS, HTTP_TIMEOUT_MS, HTTP_TIMEOUT_MS, HTTP_TIMEOUT_MS
    http.Open "POST", endpoint, False
    http.SetRequestHeader "Content-Type", "application/json"
    http.SetRequestHeader "Accept", "application/json"
    http.Send requestBody

    responseText = CStr(http.ResponseText)
    apiStatus = JsonString(responseText, "status")
    apiMessage = JsonString(responseText, "message")

    If CLng(http.Status) < 200 Or CLng(http.Status) >= 300 Or Not JsonBoolean(responseText, "success", False) Then
        errorMessage = "Device registration API error: HTTP " & CStr(http.Status)
        If Len(apiStatus) > 0 Then errorMessage = errorMessage & vbCrLf & "Status: " & apiStatus
        If Len(apiMessage) > 0 Then errorMessage = errorMessage & vbCrLf & apiMessage
        Exit Function
    End If

    If Not JsonBoolean(responseText, "registered", False) Then
        registrationUrl = JsonString(responseText, "registration_url")
        errorMessage = apiMessage
        If Len(errorMessage) = 0 Then errorMessage = "ERP device registration complete nahi hua."
        If Len(registrationUrl) > 0 Then
            If MsgBox(errorMessage & vbCrLf & vbCrLf & "Registration page kholna chahte hain?", vbQuestion + vbYesNo, API_PROMPT_TITLE) = vbYes Then
                ThisWorkbook.FollowHyperlink registrationUrl
            End If
        End If
        Exit Function
    End If

    clientToken = Trim$(JsonString(responseText, "client_token"))
    If Len(clientToken) < 32 Then
        errorMessage = "Server ne valid device token return nahi kiya."
        Exit Function
    End If

    SaveSetting TOKEN_SETTINGS_APP, TOKEN_SETTINGS_SECTION, operatorMobile, clientToken
    EnsureErpClientToken = True
    Exit Function

RegistrationError:
    errorMessage = "Automatic device registration complete nahi ho saka." & vbCrLf & Err.Description
End Function

Public Sub ResetStoredErpDeviceToken()
    Dim operatorMobile As String

    If Not TryGetOperatorMobile(operatorMobile) Then
        MsgBox "User sheet ke B1 me valid Operator Mobile nahi hai.", vbExclamation, API_PROMPT_TITLE
        Exit Sub
    End If

    DeleteSetting TOKEN_SETTINGS_APP, TOKEN_SETTINGS_SECTION, operatorMobile
    MsgBox "Is Windows user ka saved ERP device token remove kar diya gaya hai.", vbInformation, API_PROMPT_TITLE
End Sub
Private Function ApiBaseUrl() As String
    If USE_LOCAL_SERVER Then
        ApiBaseUrl = LOCAL_BASE_URL
    Else
        ApiBaseUrl = PRODUCTION_BASE_URL
    End If
End Function

Private Function OnlyDigits(ByVal value As String) As String
    Dim index As Long
    Dim character As String

    For index = 1 To Len(value)
        character = Mid$(value, index, 1)
        If character >= "0" And character <= "9" Then OnlyDigits = OnlyDigits & character
    Next index
End Function

Private Function JsonEscape(ByVal value As String) As String
    value = Replace(value, "\", "\\")
    value = Replace(value, Chr$(34), "\" & Chr$(34))
    value = Replace(value, vbCrLf, "\n")
    value = Replace(value, vbCr, "\n")
    value = Replace(value, vbLf, "\n")
    JsonEscape = value
End Function

Private Function JsonString(ByVal json As String, ByVal key As String) As String
    Dim valueStart As Long
    Dim index As Long
    Dim character As String
    Dim escaped As Boolean
    Dim hexValue As String
    Dim codePoint As Long

    valueStart = JsonValueStart(json, key)
    If valueStart = 0 Then Exit Function
    If LCase$(Mid$(json, valueStart, 4)) = "null" Then Exit Function
    If Mid$(json, valueStart, 1) <> Chr$(34) Then Exit Function

    index = valueStart + 1
    Do While index <= Len(json)
        character = Mid$(json, index, 1)
        If escaped Then
            Select Case character
                Case Chr$(34), "\", "/": JsonString = JsonString & character
                Case "b": JsonString = JsonString & Chr$(8)
                Case "f": JsonString = JsonString & Chr$(12)
                Case "n": JsonString = JsonString & vbLf
                Case "r": JsonString = JsonString & vbCr
                Case "t": JsonString = JsonString & vbTab
                Case "u"
                    hexValue = Mid$(json, index + 1, 4)
                    If Len(hexValue) = 4 Then
                        codePoint = CLng("&H" & hexValue)
                        If codePoint > 32767 Then codePoint = codePoint - 65536
                        JsonString = JsonString & ChrW$(codePoint)
                        index = index + 4
                    End If
                Case Else: JsonString = JsonString & character
            End Select
            escaped = False
        ElseIf character = "\" Then
            escaped = True
        ElseIf character = Chr$(34) Then
            Exit Function
        Else
            JsonString = JsonString & character
        End If
        index = index + 1
    Loop
End Function

Private Function JsonBoolean(ByVal json As String, ByVal key As String, ByVal defaultValue As Boolean) As Boolean
    Dim valueStart As Long
    valueStart = JsonValueStart(json, key)
    If valueStart = 0 Then
        JsonBoolean = defaultValue
    ElseIf LCase$(Mid$(json, valueStart, 4)) = "true" Then
        JsonBoolean = True
    ElseIf LCase$(Mid$(json, valueStart, 5)) = "false" Then
        JsonBoolean = False
    Else
        JsonBoolean = defaultValue
    End If
End Function

Private Function JsonLong(ByVal json As String, ByVal key As String, ByVal defaultValue As Long) As Long
    Dim valueStart As Long
    Dim valueEnd As Long
    Dim rawValue As String

    valueStart = JsonValueStart(json, key)
    If valueStart = 0 Then JsonLong = defaultValue: Exit Function
    valueEnd = valueStart
    Do While valueEnd <= Len(json) And InStr(1, "-0123456789", Mid$(json, valueEnd, 1), vbBinaryCompare) > 0
        valueEnd = valueEnd + 1
    Loop
    rawValue = Mid$(json, valueStart, valueEnd - valueStart)
    If IsNumeric(rawValue) Then JsonLong = CLng(rawValue) Else JsonLong = defaultValue
End Function

Private Function JsonIsoDate(ByVal json As String, ByVal key As String) As Date
    Dim value As String
    value = JsonString(json, key)
    If Len(value) >= 10 Then
        JsonIsoDate = DateSerial(CInt(Left$(value, 4)), CInt(Mid$(value, 6, 2)), CInt(Mid$(value, 9, 2)))
    End If
End Function

Private Function JsonValueStart(ByVal json As String, ByVal key As String) As Long
    Dim keyPosition As Long
    Dim colonPosition As Long
    Dim index As Long
    Dim character As String

    keyPosition = InStr(1, json, Chr$(34) & key & Chr$(34), vbTextCompare)
    If keyPosition = 0 Then Exit Function
    colonPosition = InStr(keyPosition + Len(key) + 2, json, ":", vbBinaryCompare)
    If colonPosition = 0 Then Exit Function

    index = colonPosition + 1
    Do While index <= Len(json)
        character = Mid$(json, index, 1)
        If character <> " " And character <> vbTab And character <> vbCr And character <> vbLf Then
            JsonValueStart = index
            Exit Function
        End If
        index = index + 1
    Loop
End Function
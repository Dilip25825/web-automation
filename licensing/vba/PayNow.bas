Attribute VB_Name = "PayNow"
Option Explicit
Private Const BASE_URL As String = "https://webautomationexcel.com"
'Private Const BASE_URL As String = "http://127.0.0.1:8000"
Private Const APP_NAME As String = "WebAutomationWithExcel"
Private Const ERP_PAYMENT_SECTION As String = "ERPPayment"
Private Const ERP_TOKEN_KEY As String = "PendingPaymentToken"
Sub MakePaymentRibben(control As IRibbonControl)
    Call MakePayment
End Sub


Public Sub MakePayment()

    On Error GoTo ErrorHandler

    Dim http As Object
    Dim RecordID As String
    Dim csrfToken As String
    Dim requestBody As String
    Dim responseText As String
    Dim paymentURL As String
    Dim paymentToken As String
    Dim isPaid As String

    '==================================================
    ' STEP 1: DATABASE RECORD ID
    ' User!B1 = tblPacsErp.ID
    '==================================================
    RecordID = Trim$(CStr(ThisWorkbook.Worksheets("User").Range("B4").Value2))

    If Len(RecordID) = 0 Then

        MsgBox "ERP database ID User sheet me available nahi hai.", _
               vbExclamation, _
               "ERP Payment"

        Exit Sub

    End If

    If Not IsNumeric(RecordID) Then

        MsgBox "ERP database ID numeric honi chahiye." & _
               vbCrLf & _
               "Current value: " & RecordID, _
               vbExclamation, _
               "ERP Payment"

        Exit Sub

    End If

    If CDbl(RecordID) <= 0 Then

        MsgBox "ERP database ID valid nahi hai.", _
               vbExclamation, _
               "ERP Payment"

        Exit Sub

    End If

    Set http = CreateObject("MSXML2.XMLHTTP.6.0")

    '==================================================
    ' STEP 2: CSRF TOKEN REQUEST
    ' Sequence: Open ? Headers ? Send
    '==================================================
    http.Open "GET", _
              BASE_URL & "/api/payments/csrf/", _
              False

    http.SetRequestHeader _
        "Accept", "application/json"

    http.Send

    If http.Status <> 200 Then

        err.Raise vbObjectError + 1001, _
                  "MakePayment", _
                  "CSRF API error: HTTP " & _
                  http.Status & vbCrLf & _
                  http.responseText

    End If

    csrfToken = GetJsonValue( _
        http.responseText, _
        "csrf_token")

    If Len(csrfToken) = 0 Then

        err.Raise vbObjectError + 1002, _
                  "MakePayment", _
                  "CSRF token server response me nahi mila." & _
                  vbCrLf & http.responseText

    End If

    ' Database ID numeric JSON value ?? ??? ??? ?????
    requestBody = _
        "{""record_id"":" & CLng(RecordID) & "}"

    '==================================================
    ' STEP 3: ERP PAYMENT REQUEST
    ' ??? HTTP object ?? ?????? Open ????
    '==================================================
    http.Open "POST", _
              BASE_URL & "/api/payments/erp/create/", _
              False

    ' Headers ????? Open ?? ??? ?? Send ?? ????
    http.SetRequestHeader "Content-Type", "application/json"
    http.SetRequestHeader "Accept", "application/json"
    http.SetRequestHeader "X-CSRFToken", csrfToken
    http.SetRequestHeader "Origin", BASE_URL
    http.SetRequestHeader "Referer", BASE_URL & "/"

    ' ??? headers ?? ??? Send
    http.Send requestBody

    responseText = http.responseText

    If http.Status < 200 Or http.Status >= 300 Then

        err.Raise vbObjectError + 1003, _
                  "MakePayment", _
                  "Payment API error: HTTP " & _
                  http.Status & vbCrLf & _
                  responseText

    End If

  '==================================================
' STEP 4: SERVER RESPONSE
' Payment URL ?? ???? ???? priority ???
'==================================================
    paymentURL = Trim$(GetJsonValue(responseText, "payment_url"))
    paymentToken = Trim$(GetJsonValue(responseText, "payment_token"))
    If LCase$(paymentURL) = "null" Then
        paymentURL = vbNullString
    End If

    If LCase$(paymentToken) = "null" Then
        paymentToken = vbNullString
    End If

isPaid = LCase$(Trim$( _
    GetJsonValue(responseText, "paid")))

Dim alreadyPaid As String
Dim isActive As String
Dim renewalRequired As String

alreadyPaid = LCase$(Trim$( _
    GetJsonValue(responseText, "already_paid")))

isActive = LCase$(Trim$( _
    GetJsonValue(responseText, "active")))

renewalRequired = LCase$(Trim$( _
    GetJsonValue(responseText, "renewal_required")))

' Fresh activation/renewal Payment Link ???? ??
If Len(paymentURL) > 0 Then

    If Len(paymentToken) = 0 Then

        err.Raise vbObjectError + 1005, _
                  "MakePayment", _
                  "Payment status token nahi mila."

    End If

    SaveSetting _
        APP_NAME, _
        ERP_PAYMENT_SECTION, _
        ERP_TOKEN_KEY, _
        paymentToken

    ThisWorkbook.FollowHyperlink _
        Address:=paymentURL, _
        NewWindow:=True

    Exit Sub

End If

' ???? active ?? unexpired ERP ?? already paid ?????
If isPaid = "true" And _
   alreadyPaid = "true" And _
   isActive = "true" Then

    ClearPendingErpPayment

    MsgBox "ERP payment already complete hai." & _
           vbCrLf & _
           "ERP activation abhi active hai.", _
           vbInformation, _
           "ERP Already Active"

    Exit Sub

End If

' Expired paid record ?? link ????? ?????
If renewalRequired = "true" Then

    err.Raise vbObjectError + 1006, _
              "MakePayment", _
              "ERP renewal required hai, lekin fresh payment link nahi mili." & _
              vbCrLf & _
              "Backend deployment check karein."

End If

err.Raise vbObjectError + 1007, _
          "MakePayment", _
          "Server se valid ERP payment response nahi mila." & _
          vbCrLf & responseText

    '==================================================
    ' STEP 5: NEXT LOGIN FALLBACK
    '==================================================
    SaveSetting _
        APP_NAME, _
        ERP_PAYMENT_SECTION, _
        ERP_TOKEN_KEY, _
        paymentToken

    '==================================================
    ' STEP 6: OPEN RAZORPAY PAGE
    '==================================================
    ThisWorkbook.FollowHyperlink _
        Address:=paymentURL, _
        NewWindow:=True

    Exit Sub

ErrorHandler:

    MsgBox "ERP payment start nahi ho saka:" & _
           vbCrLf & _
           err.Description, _
           vbCritical, _
           "Payment Error"

End Sub

'==========================================================
' CALL THIS FUNCTION BEFORE ERP LOGIN DATABASE CHECK
'==========================================================
Public Function CheckPendingErpPayment() As Boolean

    On Error GoTo ErrorHandler

    Dim http As Object
    Dim paymentToken As String
    Dim responseText As String
    Dim isPaid As String
    Dim newRecordID As String

    CheckPendingErpPayment = False

    paymentToken = GetSetting( _
        APP_NAME, _
        ERP_PAYMENT_SECTION, _
        ERP_TOKEN_KEY, _
        vbNullString)

    If Len(paymentToken) = 0 Then Exit Function

    Set http = CreateObject("MSXML2.XMLHTTP.6.0")

    ' GET request ??, ????? CSRF/Referer ?? ????? ????
    http.Open "GET", _
              BASE_URL & _
              "/api/payments/erp/status/?token=" & _
              UrlEncodeValue(paymentToken), _
              False

    http.SetRequestHeader "Accept", "application/json"
    http.Send

    responseText = http.responseText

    If http.Status < 200 Or http.Status >= 300 Then

    If InStr(1, responseText, "INVALID_TOKEN", vbTextCompare) > 0 Or _
       InStr(1, responseText, "TOKEN_EXPIRED", vbTextCompare) > 0 Or _
       InStr(1, responseText, "STALE_TOKEN", vbTextCompare) > 0 Or _
       InStr(1, responseText, "TOKEN_RECORD_MISMATCH", vbTextCompare) > 0 Then

        ' ?????? token ?? ????? normal expiry/payment flow ???? ???
        ClearPendingErpPayment
        CheckPendingErpPayment = False
        Exit Function

    End If

    err.Raise vbObjectError + 1201, _
              "CheckPendingErpPayment", _
              "Payment status error: HTTP " & _
              http.Status & vbCrLf & _
              responseText

End If

    isPaid = LCase$(Trim$( _
        GetJsonValue(responseText, "paid")))

    If isPaid = "true" Then

        newRecordID = Trim$( _
            GetJsonValue(responseText, "record_id"))

        If Len(newRecordID) = 0 Or _
           Not IsNumeric(newRecordID) Then

            err.Raise vbObjectError + 1202, _
                      "CheckPendingErpPayment", _
                      "Activated ERP ki new database ID nahi mili."

        End If

        ' Renewal ?? ?? active database ID save ????
        Sheets("user").Unprotect "Pacs#Erp"
        ThisWorkbook.Worksheets("User") _
            .Range("B1").Value2 = CLng(newRecordID)
        Sheets("user").Protect "Pacs#Erp"
        ClearPendingErpPayment
        CheckPendingErpPayment = True

        MsgBox "Payment successfully verify ho gayi." & _
               vbCrLf & _
               "ERP activation renew ho gayi hai." & _
               vbCrLf & _
               "New database ID: " & newRecordID, _
               vbInformation, _
               "ERP Activated"

    End If

    Exit Function

ErrorHandler:

    'MsgBox "ERP payment verify nahi ho saki:" & _
           vbCrLf & _
           err.Description, _
           vbExclamation, _
           "ERP Payment Verification"

    CheckPendingErpPayment = False

End Function
'==========================================================
' CLEAR SAVED PAYMENT TOKEN
'==========================================================
Private Sub ClearPendingErpPayment()

    On Error Resume Next

    DeleteSetting _
        APP_NAME, _
        ERP_PAYMENT_SECTION, _
        ERP_TOKEN_KEY

    On Error GoTo 0

End Sub
'==========================================================
' READ VALUE FROM SIMPLE JSON RESPONSE
'==========================================================
Private Function GetJsonValue( _
    ByVal jsonText As String, _
    ByVal keyName As String) As String

    Dim keyPosition As Long
    Dim valueStart As Long
    Dim valueEnd As Long
    Dim currentCharacter As String

    keyPosition = InStr( _
        1, _
        jsonText, _
        """" & keyName & """", _
        vbTextCompare)

    If keyPosition = 0 Then Exit Function

    valueStart = InStr( _
        keyPosition, _
        jsonText, _
        ":")

    If valueStart = 0 Then Exit Function

    valueStart = valueStart + 1

    ' Spaces ?????
    Do While valueStart <= Len(jsonText)

        currentCharacter = _
            Mid$(jsonText, valueStart, 1)

        If currentCharacter <> " " And _
           currentCharacter <> vbTab And _
           currentCharacter <> vbCr And _
           currentCharacter <> vbLf Then

            Exit Do

        End If

        valueStart = valueStart + 1

    Loop

    ' JSON string value
    If Mid$(jsonText, valueStart, 1) = """" Then

        valueStart = valueStart + 1
        valueEnd = valueStart

        Do While valueEnd <= Len(jsonText)

            If Mid$(jsonText, valueEnd, 1) = """" And _
               Mid$(jsonText, valueEnd - 1, 1) <> "\" Then

                Exit Do

            End If

            valueEnd = valueEnd + 1

        Loop

        GetJsonValue = Mid$( _
            jsonText, _
            valueStart, _
            valueEnd - valueStart)

        GetJsonValue = Replace( _
            GetJsonValue, "\/", "/")

        GetJsonValue = Replace( _
            GetJsonValue, "\""", """")

        GetJsonValue = Replace( _
            GetJsonValue, "\r", vbCr)

        GetJsonValue = Replace( _
            GetJsonValue, "\n", vbLf)

    Else

        ' Boolean ?? numeric value
        valueEnd = valueStart

        Do While valueEnd <= Len(jsonText)

            currentCharacter = _
                Mid$(jsonText, valueEnd, 1)

            If currentCharacter = "," Or _
               currentCharacter = "}" Then

                Exit Do

            End If

            valueEnd = valueEnd + 1

        Loop

        GetJsonValue = Trim$(Mid$( _
            jsonText, _
            valueStart, _
            valueEnd - valueStart))

    End If
    
    
    If LCase$(Trim$(GetJsonValue)) = "null" Then
    GetJsonValue = vbNullString
End If
    

End Function

'==========================================================
' JSON ESCAPE
'==========================================================
Private Function JsonEscape( _
    ByVal value As String) As String

    value = Replace(value, "\", "\\")
    value = Replace(value, """", "\""")
    value = Replace(value, vbCr, "\r")
    value = Replace(value, vbLf, "\n")

    JsonEscape = value

End Function

'==========================================================
' URL ENCODE PAYMENT TOKEN
'==========================================================
Private Function UrlEncodeValue( _
    ByVal value As String) As String

    On Error GoTo Fallback

    UrlEncodeValue = _
        Application.WorksheetFunction.EncodeURL(value)

    Exit Function

Fallback:

    ' Django signed token ????????? URL-safe ???? ??
    value = Replace(value, "%", "%25")
    value = Replace(value, "+", "%2B")
    value = Replace(value, "=", "%3D")
    value = Replace(value, ":", "%3A")
    value = Replace(value, "/", "%2F")
    value = Replace(value, "?", "%3F")
    value = Replace(value, "&", "%26")

    UrlEncodeValue = value

End Function

Sub MakePaymentstop()
 Dim upiID As String, name As String, amount As String, message As String
    Dim upiLink As String
    Dim qrCodeUrl As String
    Dim erpID As String

   ' On Error GoTo ErrorHandler

    ' Set your UPI details
    upiID = getUpiID
    name = "Web Automation With Excel"
    amount = "" ' paymentFromServer ' Make sure paymentFromServer is properly defined
    'message = "ERP " & DeleteUid(Range("userID"))
    erpID = CStr(Range("B5"))
    message = "ERP " & erpID
    ' Create UPI payment link
    upiLink = "upi://pay?pa=" & upiID & "&pn=" & URLEncode(name) & "&am=" & amount & "&tn=" & URLEncode(message)

    ' API endpoint for QR code generation (using a more reliable free service)
    qrCodeUrl = "https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=" & URLEncode(upiLink)

    ThisWorkbook.FollowHyperlink qrCodeUrl
    'ThisWorkbook.FollowHyperlink getUpiID
End Sub
'
'Public Function GetErpUserIdForPayment(ByVal ID As Long) As String
'    Dim rs As Object
'    Dim openedHere As Boolean
'
'    On Error GoTo Failed
'
'    If con.State <> 1 Then ConnectionToMysqlDataBase
'
'    Set rs = con.Execute( _
'        "SELECT erpId FROM tblPacsErp " & _
'        "WHERE ID = " & CStr(ID) & " LIMIT 1")
'
'    If Not rs.EOF Then
'        'If Not IsNull(rs.Fields("erpId").value) Then
'            GetErpUserIdForPayment = CStr(Range("B4"))
'        'End If
'    End If
'
'CleanExit:
'    On Error Resume Next
'    If Not rs Is Nothing Then rs.Close
'    If openedHere Then con.Close
'    Exit Function
'
'Failed:
'    GetErpUserIdForPayment = vbNullString
'    Resume CleanExit
'End Function


Private Function URLEncode(ByVal str As String) As String
    Dim i As Integer, tempStr As String, char As String
    tempStr = ""

    For i = 1 To Len(str)
        char = Mid(str, i, 1)

        Select Case char
            Case "A" To "Z", "a" To "z", "0" To "9", "-", "_", ".", "~"
                tempStr = tempStr & char
            Case " "
                tempStr = tempStr & "+"
            Case Else
                tempStr = tempStr & "%" & Right("0" & Hex(Asc(char)), 2)
        End Select
    Next i

    URLEncode = tempStr
End Function

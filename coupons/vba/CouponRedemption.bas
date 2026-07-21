Attribute VB_Name = "CouponRedemption"
Option Explicit

Private Const COUPON_API_BASE_URL As String = "https://web-automation-maar.onrender.com"

' Ribbon XML example:
' <button id="btnApplyCoupon" label="Apply Coupon" imageMso="HappyFace"
'         size="large" onAction="ApplyCustomerCoupon"/>
Public Sub ApplyCustomerCoupon(ByVal control As IRibbonControl)
    Dim couponCode As String
    Dim userID As String
    Dim serviceName As String
    Dim financialYear As String
    Dim csrfToken As String
    Dim csrfCookie As String
    Dim requestBody As String
    Dim responseText As String
    Dim discountAmount As String
    Dim oldAmount As String
    Dim newAmount As String

    On Error GoTo ErrorHandler

    couponCode = Trim$(InputBox( _
        "Paste your coupon code:" & vbCrLf & _
        "Example: SAVE750-TFS1X-EFYTD", _
        "Apply Coupon"))
    If couponCode = "" Then Exit Sub
    couponCode = UCase$(couponCode)

    userID = Trim$(CStr(ThisWorkbook.Worksheets("User").Range("B4").Value))
    serviceName = "PMFBY"
    financialYear = Trim$(CStr(ThisWorkbook.Worksheets("Seeting").Range("B4").Value))

    If userID = "" Or Not IsNumeric(userID) Then
        MsgBox "A valid User ID was not found in User!B4.", vbExclamation, "Coupon"
        Exit Sub
    End If
    If financialYear = "" Then
        MsgBox "Financial year was not found in Seeting!B4.", vbExclamation, "Coupon"
        Exit Sub
    End If

    Application.StatusBar = "Validating coupon..."
    GetCouponCSRF csrfToken, csrfCookie

    requestBody = "{""coupon_code"":""" & JsonEscape(couponCode) & """," & _
                  """user_id"":""" & JsonEscape(userID) & """," & _
                  """service"":""" & JsonEscape(serviceName) & """," & _
                  """financial_year"":""" & JsonEscape(financialYear) & """}"

    responseText = RedeemCouponRequest(requestBody, csrfToken, csrfCookie)
    discountAmount = JsonNumber(responseText, "discount_amount")
    oldAmount = JsonNumber(responseText, "old_amount")
    newAmount = JsonNumber(responseText, "new_amount")

    Application.StatusBar = False
    MsgBox "Coupon applied successfully." & vbCrLf & vbCrLf & _
           "Coupon: " & couponCode & vbCrLf & _
           "Discount: Rs. " & discountAmount & vbCrLf & _
           "Old amount: Rs. " & oldAmount & vbCrLf & _
           "New amount: Rs. " & newAmount, vbInformation, "Coupon Applied"
    Exit Sub

ErrorHandler:
    Application.StatusBar = False
    MsgBox "Coupon could not be applied:" & vbCrLf & Err.Description, vbCritical, "Coupon Error"
End Sub

Private Sub GetCouponCSRF(ByRef csrfToken As String, ByRef csrfCookie As String)
    Dim http As Object
    Dim setCookie As String
    Set http = CreateObject("WinHttp.WinHttpRequest.5.1")
    http.Open "GET", COUPON_API_BASE_URL & "/api/coupons/csrf/", False
    http.SetRequestHeader "Accept", "application/json"
    http.Send
    If http.Status <> 200 Then
        Err.Raise vbObjectError + 2100, "GetCouponCSRF", _
                  "CSRF API error: HTTP " & http.Status & vbCrLf & http.ResponseText
    End If
    csrfToken = JsonString(http.ResponseText, "csrf_token")
    On Error Resume Next
    setCookie = http.GetResponseHeader("Set-Cookie")
    On Error GoTo 0
    csrfCookie = FirstCookie(setCookie)
    If csrfToken = "" Or csrfCookie = "" Then
        Err.Raise vbObjectError + 2101, "GetCouponCSRF", "CSRF token or cookie was not received."
    End If
End Sub

Private Function RedeemCouponRequest(ByVal requestBody As String, ByVal csrfToken As String, ByVal csrfCookie As String) As String
    Dim http As Object
    Dim apiError As String
    Set http = CreateObject("WinHttp.WinHttpRequest.5.1")
    http.Open "POST", COUPON_API_BASE_URL & "/api/coupons/redeem/", False
    http.SetRequestHeader "Content-Type", "application/json"
    http.SetRequestHeader "Accept", "application/json"
    http.SetRequestHeader "X-CSRFToken", csrfToken
    http.SetRequestHeader "Cookie", csrfCookie
    http.SetRequestHeader "Referer", COUPON_API_BASE_URL & "/"
    http.Send requestBody
    If http.Status < 200 Or http.Status >= 300 Then
        apiError = JsonString(http.ResponseText, "error")
        If apiError = "" Then apiError = http.ResponseText
        Err.Raise vbObjectError + 2110, "RedeemCouponRequest", apiError & " (HTTP " & http.Status & ")"
    End If
    RedeemCouponRequest = http.ResponseText
End Function

Private Function FirstCookie(ByVal setCookie As String) As String
    Dim firstLine As String
    Dim semicolonPosition As Long
    firstLine = Split(setCookie, vbCrLf)(0)
    semicolonPosition = InStr(1, firstLine, ";")
    If semicolonPosition > 0 Then
        FirstCookie = Left$(firstLine, semicolonPosition - 1)
    Else
        FirstCookie = firstLine
    End If
End Function

Private Function JsonString(ByVal jsonText As String, ByVal propertyName As String) As String
    Dim regex As Object
    Dim matches As Object
    Set regex = CreateObject("VBScript.RegExp")
    regex.Pattern = """" & propertyName & """\s*:\s*""((?:\\.|[^""])*)"""
    regex.Global = False
    regex.IgnoreCase = True
    Set matches = regex.Execute(jsonText)
    If matches.Count > 0 Then
        JsonString = matches(0).SubMatches(0)
        JsonString = Replace(JsonString, "\/", "/")
        JsonString = Replace(JsonString, "\""", """")
        JsonString = Replace(JsonString, "\\", "\")
    End If
End Function

Private Function JsonNumber(ByVal jsonText As String, ByVal propertyName As String) As String
    Dim regex As Object
    Dim matches As Object
    Set regex = CreateObject("VBScript.RegExp")
    regex.Pattern = """" & propertyName & """\s*:\s*(-?\d+(?:\.\d+)?)"
    regex.Global = False
    regex.IgnoreCase = True
    Set matches = regex.Execute(jsonText)
    If matches.Count > 0 Then JsonNumber = matches(0).SubMatches(0)
End Function

Private Function JsonEscape(ByVal value As String) As String
    value = Replace(value, "\", "\\")
    value = Replace(value, """", "\""")
    value = Replace(value, vbCrLf, "\n")
    value = Replace(value, vbCr, "\n")
    value = Replace(value, vbLf, "\n")
    JsonEscape = value
End Function

Attribute VB_Name = "ErpCouponRedemption"
Option Explicit

' Requires the existing ErpApiLogin module. Add the ribbon callback below:
' <button id="btnApplyErpCoupon" label="Apply ERP Coupon" imageMso="HappyFace"
'         size="large" onAction="ApplyErpCoupon"/>
'
' The API authenticates with the existing device-bound ERP token; no server
' secret is embedded in this workbook.
Private Const ERP_COUPON_ENDPOINT As String = "/api/licensing/erp/coupon/redeem/"
Private Const ERP_COUPON_TIMEOUT_MS As Long = 90000

Public Sub ApplyErpCoupon(ByVal control As IRibbonControl)
    Dim couponCode As String
    Dim operatorMobile As String
    Dim clientToken As String
    Dim errorMessage As String
    Dim requestBody As String
    Dim responseText As String
    Dim http As Object
    Dim apiStatus As String
    Dim apiMessage As String

    On Error GoTo CouponError

    couponCode = UCase$(Trim$(InputBox("Paste ERP coupon code:", "Apply ERP Coupon")))
    If Len(couponCode) = 0 Then Exit Sub

    If Not GetErpApiCredentials(operatorMobile, clientToken, errorMessage) Then
        MsgBox errorMessage, vbExclamation, "ERP Coupon"
        Exit Sub
    End If

    requestBody = "{""operator_mobile"":""" & ErpCouponJsonEscape(operatorMobile) & """,""coupon_code"":""" & ErpCouponJsonEscape(couponCode) & """}"
    Set http = CreateObject("WinHttp.WinHttpRequest.5.1")
    http.SetTimeouts ERP_COUPON_TIMEOUT_MS, ERP_COUPON_TIMEOUT_MS, ERP_COUPON_TIMEOUT_MS, ERP_COUPON_TIMEOUT_MS
    http.Open "POST", ErpApiBaseUrl() & ERP_COUPON_ENDPOINT, False
    http.SetRequestHeader "Content-Type", "application/json"
    http.SetRequestHeader "Accept", "application/json"
    http.SetRequestHeader "Authorization", "Bearer " & clientToken
    http.Send requestBody

    responseText = CStr(http.ResponseText)
    If CLng(http.Status) < 200 Or CLng(http.Status) >= 300 Or Not ErpCouponJsonBoolean(responseText, "success") Then
        apiStatus = UCase$(ErpCouponJsonString(responseText, "status"))
        apiMessage = ErpCouponJsonString(responseText, "message")
        If Len(apiMessage) = 0 Then apiMessage = "Coupon apply nahi ho saka."
        MsgBox apiMessage & vbCrLf & "Status: " & apiStatus, vbExclamation, "ERP Coupon"
        Exit Sub
    End If

    MsgBox "ERP coupon successfully apply ho gaya hai." & vbCrLf & vbCrLf & _
           "Coupon: " & ErpCouponJsonString(responseText, "coupon_code") & vbCrLf & _
           "Discount: Rs. " & ErpCouponJsonString(responseText, "discount_amount") & vbCrLf & _
           "New payable amount: Rs. " & ErpCouponJsonString(responseText, "current_amount"), _
           vbInformation, "ERP Coupon Applied"
    Exit Sub

CouponError:
    MsgBox "ERP coupon service se connection nahi ho saka." & vbCrLf & Err.Description, vbExclamation, "ERP Coupon"
End Sub

Private Function ErpCouponJsonEscape(ByVal value As String) As String
    value = Replace(value, "\", "\\")
    value = Replace(value, Chr$(34), "\" & Chr$(34))
    ErpCouponJsonEscape = Replace(value, vbCrLf, "\n")
End Function

Private Function ErpCouponJsonBoolean(ByVal json As String, ByVal key As String) As Boolean
    ErpCouponJsonBoolean = (LCase$(ErpCouponJsonRawValue(json, key)) = "true")
End Function

Private Function ErpCouponJsonString(ByVal json As String, ByVal key As String) As String
    Dim raw As String
    raw = ErpCouponJsonRawValue(json, key)
    If Left$(raw, 1) = Chr$(34) And Right$(raw, 1) = Chr$(34) Then
        ErpCouponJsonString = Mid$(raw, 2, Len(raw) - 2)
        ErpCouponJsonString = Replace(ErpCouponJsonString, "\" & Chr$(34), Chr$(34))
    Else
        ErpCouponJsonString = raw
    End If
End Function

Private Function ErpCouponJsonRawValue(ByVal json As String, ByVal key As String) As String
    Dim position As Long, startAt As Long, endAt As Long
    position = InStr(1, json, Chr$(34) & key & Chr$(34), vbTextCompare)
    If position = 0 Then Exit Function
    startAt = InStr(position, json, ":") + 1
    Do While startAt <= Len(json) And InStr(" " & vbTab & vbCr & vbLf, Mid$(json, startAt, 1)) > 0
        startAt = startAt + 1
    Loop
    If Mid$(json, startAt, 1) = Chr$(34) Then
        endAt = InStr(startAt + 1, json, Chr$(34))
        If endAt > startAt Then ErpCouponJsonRawValue = Mid$(json, startAt, endAt - startAt + 1)
    Else
        endAt = InStr(startAt, json & ",", ",")
        ErpCouponJsonRawValue = Trim$(Mid$(json, startAt, endAt - startAt))
    End If
End Function

Attribute VB_Name = "CouponRedemption"
Option Explicit

' ConnectionToMysqlDataBase must open the existing global ADODB connection named con.
' If your global connection variable has another name, replace con in this module.
Private Const AD_PARAM_INPUT As Long = 1
Private Const AD_INTEGER As Long = 3
Private Const AD_CURRENCY As Long = 6
Private Const AD_VAR_CHAR As Long = 200

' Ribbon XML:
' <button id="btnApplyCoupon" label="Apply Coupon" imageMso="HappyFace"
'         size="large" onAction="ApplyCustomerCoupon"/>
Public Sub ApplyCustomerCoupon(ByVal control As IRibbonControl)
    Dim couponCode As String
    Dim userInfoID As String
    Dim couponID As Long
    Dim discountAmount As Currency
    Dim oldAmount As Currency
    Dim newAmount As Currency
    Dim paymentStatus As Currency
    Dim cmd As Object
    Dim affectedRows As Variant
    Dim sqlText As String
    Dim errorMessage As String

    On Error GoTo ErrorHandler

    couponCode = UCase$(Trim$(InputBox( _
        "Paste your coupon code:" & vbCrLf & _
        "Example: C750-ABCDE-FGHIJ-KLMNO-PQRST-UVWXYZ", _
        "Apply Coupon")))
    If couponCode = "" Then Exit Sub

    ' User!B4 contains userinfo.ID, not Mobile.
    userInfoID = Trim$(CStr(ThisWorkbook.Worksheets("User").Range("B4").Value))
    If userInfoID = "" Or Not IsNumeric(userInfoID) Then
        MsgBox "A valid UserInfo ID was not found in User!B4.", vbExclamation, "Coupon"
        Exit Sub
    End If

    Application.StatusBar = "Validating coupon..."
    ' Do not reopen an already-open global connection.
    If con Is Nothing Then
        ConnectionToMysqlDataBase
    ElseIf con.State <> 1 Then
        ConnectionToMysqlDataBase
    End If
    If con Is Nothing Then Err.Raise vbObjectError + 2200, , "MySQL connection was not created."
    If con.State <> 1 Then Err.Raise vbObjectError + 2201, , "MySQL connection is closed."

    ' Release any recordset left open by the shared connection routine.
    On Error Resume Next
    If Not rst Is Nothing Then
        If rst.State = 1 Then rst.Close
        Set rst = Nothing
    End If
    On Error GoTo ErrorHandler

    ' A single query/recordset avoids MySQL cursor conflicts in the transaction.
    ' User!B4 is matched only against userinfo.ID.
    sqlText = "SELECT u.Amount, u.PaymentStatus, c.ID AS CouponID, c.DiscountAmount, " & _
        "EXISTS(SELECT 1 FROM coupons_coupon x WHERE x.UsedBy = CAST(u.ID AS CHAR) AND x.Status = 0 LIMIT 1) AS AlreadyUsed " & _
        "FROM userinfo u JOIN coupons_coupon c ON c.CouponCode = '" & SqlEscape(couponCode) & "' " & _
        "AND c.Status = 1 AND (c.UsedBy IS NULL OR c.UsedBy LIKE 'RESERVED:%' OR c.UsedBy = CAST(u.ID AS CHAR)) WHERE u.ID = " & CStr(CLng(userInfoID)) & " LIMIT 1"
    Set rst = con.Execute(sqlText)
    If rst.EOF Then
        Err.Raise vbObjectError + 2203, , "Coupon was not found, is inactive, or is reserved for another UserInfo ID."
    End If
    If CBool(rst.Fields("AlreadyUsed").Value) Then
        Err.Raise vbObjectError + 2202, , "This user has already used a coupon."
    End If
    couponID = CLng(rst.Fields("CouponID").Value)
    discountAmount = CCur(rst.Fields("DiscountAmount").Value)
    If IsNull(rst.Fields("Amount").Value) Then
        oldAmount = 0
    Else
        oldAmount = CCur(rst.Fields("Amount").Value)
    End If
    If IsNull(rst.Fields("PaymentStatus").Value) Then
        paymentStatus = 0
    Else
        paymentStatus = CCur(rst.Fields("PaymentStatus").Value)
    End If
    rst.Close
    Set rst = Nothing

    If paymentStatus > 0 Then Err.Raise vbObjectError + 2205, , "Coupon must be applied before payment starts."
    If discountAmount <= 0 Then Err.Raise vbObjectError + 2206, , "Coupon discount amount is invalid."
    If discountAmount > oldAmount Then Err.Raise vbObjectError + 2207, , "Coupon discount is greater than the payable amount."
    newAmount = oldAmount - discountAmount

    ' Update UserInfo and coupon together in one atomic MySQL statement.
    sqlText = "UPDATE userinfo u " & _
        "JOIN coupons_coupon c ON c.ID = " & CStr(couponID) & _
        " AND c.Status = 1 AND (c.UsedBy IS NULL OR c.UsedBy LIKE 'RESERVED:%' OR c.UsedBy = CAST(u.ID AS CHAR)) " & _
        "LEFT JOIN coupons_coupon used_coupon ON used_coupon.UsedBy = CAST(u.ID AS CHAR) AND used_coupon.Status = 0 " & _
        "SET u.Amount = u.Amount - c.DiscountAmount, " & _
        "c.UsedBy = CAST(u.ID AS CHAR), c.Status = 0 " & _
        "WHERE u.ID = " & CStr(CLng(userInfoID)) & _
        " AND used_coupon.ID IS NULL " & _
        "AND (u.PaymentStatus IS NULL OR u.PaymentStatus <= 0) " & _
        "AND c.DiscountAmount > 0 AND c.DiscountAmount <= u.Amount"
    affectedRows = Empty
    con.Execute sqlText, affectedRows
    If CLng(affectedRows) < 1 Then
        Err.Raise vbObjectError + 2208, , "Coupon could not be applied because the data changed or it was already used."
    End If

    Application.StatusBar = False

    MsgBox "Coupon applied successfully." & vbCrLf & vbCrLf & _
           "UserInfo ID: " & userInfoID & vbCrLf & _
           "Coupon: " & couponCode & vbCrLf & _
           "Discount: Rs. " & Format$(discountAmount, "0.00") & vbCrLf & _
           "Old amount: Rs. " & Format$(oldAmount, "0.00") & vbCrLf & _
           "New amount: Rs. " & Format$(newAmount, "0.00"), _
           vbInformation, "Coupon Applied"
    Exit Sub

ErrorHandler:
    errorMessage = Err.Description
    On Error Resume Next
    If Not rst Is Nothing Then If rst.State = 1 Then rst.Close
    Application.StatusBar = False
    On Error GoTo 0
    MsgBox "Coupon could not be applied:" & vbCrLf & errorMessage, vbCritical, "Coupon Error"
End Sub

Private Function SqlEscape(ByVal value As String) As String
    SqlEscape = Replace(value, "'", "''")
End Function

import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase, override_settings

from . import payment_services as services
from . import payment_views as views
from .payment_services import PaymentError


SETTINGS = override_settings(SECRET_KEY='test-secret', RAZORPAY_KEY_ID='rzp_test_key', RAZORPAY_KEY_SECRET='secret', RAZORPAY_WEBHOOK_SECRET='webhook-secret', RAZORPAY_API_BASE_URL='https://api.razorpay.test/v1', PAYMENT_STATUS_TOKEN_MAX_AGE=21600)


def record(**changes):
    values = dict(pk=7, id=7, mobile=9876543210, for_whys='PMFBY', f_year='Kharif 2026', amount=2000, payment_status=0, is_active=0, activation_date=None, razorpay_payment_link_id='plink_test', razorpay_payment_id=None, razorpay_reference_id='U7-reference', razorpay_payment_status='created')
    values.update(changes)
    item = SimpleNamespace(**values)
    item.save = MagicMock()
    return item


def link(**changes):
    values = dict(id='plink_test', reference_id='U7-reference', amount=200000, currency='INR', status='paid')
    values.update(changes)
    return values


def payment(**changes):
    values = dict(id='pay_test', amount=200000, currency='INR', status='captured')
    values.update(changes)
    return values


@SETTINGS
class RazorpayPaymentTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.atomic_patcher = patch('licensing.payment_services.transaction.atomic')
        self.atomic_patcher.start()
        self.addCleanup(self.atomic_patcher.stop)

    @patch('licensing.payment_views.create_razorpay_payment_link')
    @patch('licensing.payment_views.find_payment_record')
    def test_01_valid_payment_creation(self, find, create):
        find.return_value = record(); create.return_value = {'success': True, 'amount': 200000, 'status': 'CREATED'}
        request = self.factory.post('/api/payments/create/', data=json.dumps({'user_id':'9876543210','service':'PMFBY','financial_year':'Kharif 2026'}), content_type='application/json')
        response = views.payment_create(request)
        self.assertEqual(response.status_code, 200); self.assertEqual(json.loads(response.content)['amount'], 200000)

    def test_02_missing_user_id(self):
        request=self.factory.post('/api/payments/create/',data='{}',content_type='application/json'); response=views.payment_create(request)
        self.assertEqual(response.status_code,400); self.assertEqual(json.loads(response.content)['code'],'INVALID_USER_ID')

    def test_03_invalid_service(self):
        request=self.factory.post('/api/payments/create/',data=json.dumps({'user_id':'1','financial_year':'FY'}),content_type='application/json'); response=views.payment_create(request)
        self.assertEqual(json.loads(response.content)['code'],'INVALID_SERVICE')

    def test_04_invalid_financial_year(self):
        request=self.factory.post('/api/payments/create/',data=json.dumps({'user_id':'1','service':'PMFBY'}),content_type='application/json'); response=views.payment_create(request)
        self.assertEqual(json.loads(response.content)['code'],'INVALID_FINANCIAL_YEAR')

    @patch('licensing.payment_views.create_razorpay_payment_link')
    @patch('licensing.payment_views.find_payment_record')
    def test_05_database_amount_is_authoritative(self, find, create):
        find.return_value=record(amount=2000); create.return_value={'success':True,'amount':200000}
        request=self.factory.post('/api/payments/create/',data=json.dumps({'user_id':'1','service':'PMFBY','financial_year':'FY','amount':1}),content_type='application/json'); response=views.payment_create(request)
        self.assertEqual(json.loads(response.content)['amount'],200000)
    def test_06_client_amount_is_not_a_service_argument(self):
        self.assertEqual(services.create_razorpay_payment_link.__code__.co_argcount,1)

    @patch('licensing.payment_services.UserInfoData.objects')
    def test_07_already_paid_does_not_create_link(self, objects):
        objects.select_for_update.return_value.get.return_value=record(payment_status=2000)
        with patch('licensing.payment_services._razorpay_request') as remote:
            result=services.create_razorpay_payment_link(7)
        self.assertTrue(result['already_paid']); remote.assert_not_called()

    @patch('licensing.payment_services.UserInfoData.objects')
    @patch('licensing.payment_services._razorpay_request')
    def test_08_existing_pending_link_is_reused(self, remote, objects):
        objects.select_for_update.return_value.get.return_value=record(); remote.return_value={'id':'plink_test','short_url':'https://rzp.io/test','status':'created'}
        result=services.create_razorpay_payment_link(7)
        self.assertEqual(result['payment_url'],'https://rzp.io/test'); remote.assert_called_once()

    @patch('licensing.payment_services.UserInfoData.objects')
    @patch('licensing.payment_services._razorpay_request', side_effect=PaymentError('down','RAZORPAY_API_ERROR',502))
    def test_09_razorpay_api_failure(self, remote, objects):
        objects.select_for_update.return_value.get.return_value=record(razorpay_payment_link_id=None,razorpay_reference_id=None)
        with self.assertRaises(PaymentError): services.create_razorpay_payment_link(7)

    def test_10_valid_webhook_signature(self):
        body=b'{}'; signature=hmac.new(b'webhook-secret',body,hashlib.sha256).hexdigest()
        self.assertTrue(services.verify_razorpay_webhook_signature(body,signature))

    def test_11_invalid_webhook_signature(self):
        self.assertFalse(services.verify_razorpay_webhook_signature(b'{}','bad'))

    def test_12_missing_webhook_signature(self):
        self.assertFalse(services.verify_razorpay_webhook_signature(b'{}',''))

    def test_13_wrong_payment_amount(self):
        with self.assertRaises(PaymentError) as caught: services._apply_paid_entities(record(),link(),payment(amount=199900))
        self.assertEqual(caught.exception.code,'WRONG_AMOUNT')

    def test_14_wrong_currency(self):
        with self.assertRaises(PaymentError) as caught: services._apply_paid_entities(record(),link(currency='USD'),payment(currency='USD'))
        self.assertEqual(caught.exception.code,'WRONG_CURRENCY')

    @patch('licensing.payment_services.UserInfoData.objects')
    def test_15_unknown_payment_link_id(self, objects):
        objects.select_for_update.return_value.get.side_effect=services.UserInfoData.DoesNotExist
        with self.assertRaises(PaymentError) as caught: services.process_payment_link_paid(link(id='unknown'),payment())
        self.assertEqual(caught.exception.code,'UNKNOWN_PAYMENT_LINK')

    def test_16_duplicate_webhook_is_idempotent(self):
        item=record(payment_status=2000,razorpay_payment_id='pay_test',razorpay_payment_status='paid')
        self.assertTrue(services._apply_paid_entities(item,link(),payment())); item.save.assert_not_called()

    def test_17_correct_record_is_activated(self):
        item=record(); services._apply_paid_entities(item,link(),payment())
        self.assertEqual(item.payment_status,item.amount); self.assertEqual(item.is_active,1); item.save.assert_called_once()

    def test_18_other_financial_year_is_not_derived_from_webhook_notes(self):
        item=record(); entity=link(); entity['notes']={'financial_year':'Other Year'}; services._apply_paid_entities(item,entity,payment())
        self.assertEqual(item.f_year,'Kharif 2026')

    def test_19_other_service_is_not_derived_from_webhook_notes(self):
        item=record(); entity=link(); entity['notes']={'service':'OTHER'}; services._apply_paid_entities(item,entity,payment())
        self.assertEqual(item.for_whys,'PMFBY')

    def test_20_pending_status_api_payload(self):
        result=services.get_existing_payment_status(record())
        self.assertFalse(result['paid']); self.assertEqual(result['status'],'CREATED')

    def test_21_paid_status_api_payload(self):
        result=services.get_existing_payment_status(record(payment_status=2000,razorpay_payment_status='paid'))
        self.assertTrue(result['paid']); self.assertEqual(result['status'],'PAID')

    def test_22_invalid_status_token(self):
        with self.assertRaises(PaymentError) as caught: services.record_from_token('invalid','9876543210')
        self.assertEqual(caught.exception.code,'INVALID_TOKEN')

    def test_23_unauthorized_api_request(self):
        request=self.factory.get('/api/payments/status/')
        with self.assertRaises(PaymentError) as caught: views.authenticate_license(request)
        self.assertEqual(caught.exception.code,'UNAUTHORIZED')

    def test_24_payment_status_equals_amount_after_webhook(self):
        item=record(utr_number=None); services._apply_paid_entities(item,link(),payment(acquirer_data={'rrn':'123456789012'}))
        self.assertEqual(item.payment_status,2000)
        self.assertEqual(item.utr_number,'123456789012')
        item.save.assert_called_once_with(update_fields=['utr_number', 'razorpay_payment_id', 'razorpay_payment_status', 'payment_status', 'is_active', 'activation_date'])

    @patch('licensing.payment_services.UserInfoData.objects')
    def test_25_expired_event_does_not_deactivate_paid_record(self, objects):
        item=record(payment_status=2000,is_active=1,razorpay_payment_status='paid'); objects.select_for_update.return_value.get.return_value=item
        services.process_payment_link_state(link(),'expired')
        self.assertEqual(item.is_active,1); self.assertEqual(item.razorpay_payment_status,'paid'); item.save.assert_not_called()

    @patch('licensing.payment_services.UserInfoData.objects')
    def test_cancelled_link_clears_four_razorpay_fields(self, objects):
        item=record(payment_status=0, razorpay_payment_id='pay_test'); objects.select_for_update.return_value.get.return_value=item
        services.process_payment_link_state(link(), 'cancelled')
        self.assertIsNone(item.razorpay_payment_link_id)
        self.assertIsNone(item.razorpay_payment_id)
        self.assertIsNone(item.razorpay_reference_id)
        self.assertIsNone(item.razorpay_payment_status)
        item.save.assert_called_once_with(update_fields=['razorpay_payment_link_id', 'razorpay_payment_id', 'razorpay_reference_id', 'razorpay_payment_status'])
    @patch('licensing.payment_views.process_payment_link_paid', return_value={'duplicate':False,'record_id':7})
    def test_webhook_endpoint_processes_valid_event(self, process):
        payload={'event':'payment_link.paid','payload':{'payment_link':{'entity':link()},'payment':{'entity':payment()}}}; body=json.dumps(payload).encode(); signature=hmac.new(b'webhook-secret',body,hashlib.sha256).hexdigest(); request=self.factory.post('/api/payments/razorpay/webhook/',data=body,content_type='application/json',HTTP_X_RAZORPAY_SIGNATURE=signature); response=views.razorpay_webhook(request)
        self.assertEqual(response.status_code,200); process.assert_called_once()
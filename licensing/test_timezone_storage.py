from datetime import datetime, timezone as datetime_timezone

from django.db import connection
from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils import timezone


class IndianDatabaseTimezoneTests(SimpleTestCase):
    def test_mysql_connection_uses_indian_timezone_for_datetime_storage(self):
        self.assertEqual(str(connection.timezone), 'Asia/Kolkata')

        stored_value = connection.ops.adapt_datetimefield_value(timezone.now())
        stored_datetime = datetime.fromisoformat(stored_value)
        expected = timezone.localtime(timezone.now())

        self.assertLess(abs((stored_datetime - expected.replace(tzinfo=None)).total_seconds()), 2)

    def test_userinfo_created_time_renders_in_indian_timezone(self):
        rendered = Template(
            '{% load tz %}{{ value|timezone:"Asia/Kolkata"|date:"d M Y, h:i A" }}'
        ).render(Context({'value': datetime(2026, 10, 13, 22, 3, tzinfo=datetime_timezone.utc)}))

        self.assertEqual(rendered, '14 Oct 2026, 03:33 AM')

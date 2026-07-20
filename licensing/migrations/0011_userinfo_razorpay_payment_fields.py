from django.db import migrations, models


FIELD_SQL = {
    'RazorpayPaymentLinkID': 'VARCHAR(50) NULL UNIQUE',
    'RazorpayPaymentID': 'VARCHAR(50) NULL UNIQUE',
    'RazorpayReferenceID': 'VARCHAR(40) NULL UNIQUE',
    'RazorpayPaymentStatus': 'VARCHAR(20) NULL',
}


def add_razorpay_columns(apps, schema_editor):
    connection = schema_editor.connection
    if 'userinfo' not in connection.introspection.table_names():
        return
    with connection.cursor() as cursor:
        existing = {column.name for column in connection.introspection.get_table_description(cursor, 'userinfo')}
        table = schema_editor.quote_name('userinfo')
        for name, definition in FIELD_SQL.items():
            if name not in existing:
                cursor.execute(f'ALTER TABLE {table} ADD COLUMN {schema_editor.quote_name(name)} {definition}')


def remove_razorpay_columns(apps, schema_editor):
    connection = schema_editor.connection
    if 'userinfo' not in connection.introspection.table_names():
        return
    with connection.cursor() as cursor:
        existing = {column.name for column in connection.introspection.get_table_description(cursor, 'userinfo')}
        table = schema_editor.quote_name('userinfo')
        for name in reversed(tuple(FIELD_SQL)):
            if name in existing:
                cursor.execute(f'ALTER TABLE {table} DROP COLUMN {schema_editor.quote_name(name)}')


class Migration(migrations.Migration):
    dependencies = [('licensing', '0010_userinfo_search_indexes')]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(add_razorpay_columns, remove_razorpay_columns)],
            state_operations=[
                migrations.AddField('userinfodata', 'razorpay_payment_link_id', models.CharField(blank=True, db_column='RazorpayPaymentLinkID', max_length=50, null=True, unique=True)),
                migrations.AddField('userinfodata', 'razorpay_payment_id', models.CharField(blank=True, db_column='RazorpayPaymentID', max_length=50, null=True, unique=True)),
                migrations.AddField('userinfodata', 'razorpay_reference_id', models.CharField(blank=True, db_column='RazorpayReferenceID', max_length=40, null=True, unique=True)),
                migrations.AddField('userinfodata', 'razorpay_payment_status', models.CharField(blank=True, db_column='RazorpayPaymentStatus', max_length=20, null=True)),
            ],
        )
    ]
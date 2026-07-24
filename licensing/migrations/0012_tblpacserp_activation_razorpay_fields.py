from django.db import migrations, models


FIELD_SQL = {
    'AccepteBy': 'TEXT NULL',
    'ActivationDate': 'DATETIME NULL',
    'RazorpayPaymentLinkID': 'VARCHAR(50) NULL UNIQUE',
    'RazorpayPaymentID': 'VARCHAR(50) NULL UNIQUE',
    'RazorpayReferenceID': 'VARCHAR(40) NULL UNIQUE',
    'RazorpayPaymentStatus': 'VARCHAR(20) NULL',
}


def add_erp_payment_columns(apps, schema_editor):
    connection = schema_editor.connection
    table_name = 'tblPacsErp'
    if table_name not in connection.introspection.table_names():
        return
    with connection.cursor() as cursor:
        existing = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table_name)
        }
        table = schema_editor.quote_name(table_name)
        for name, definition in FIELD_SQL.items():
            if name not in existing:
                column = schema_editor.quote_name(name)
                cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')


def remove_erp_payment_columns(apps, schema_editor):
    connection = schema_editor.connection
    table_name = 'tblPacsErp'
    if table_name not in connection.introspection.table_names():
        return
    with connection.cursor() as cursor:
        existing = {
            column.name
            for column in connection.introspection.get_table_description(cursor, table_name)
        }
        table = schema_editor.quote_name(table_name)
        for name in reversed(tuple(FIELD_SQL)):
            if name in existing:
                column = schema_editor.quote_name(name)
                cursor.execute(f'ALTER TABLE {table} DROP COLUMN {column}')


class Migration(migrations.Migration):
    dependencies = [('licensing', '0011_userinfo_razorpay_payment_fields')]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_erp_payment_columns, remove_erp_payment_columns)
            ],
            state_operations=[
                migrations.AddField('tblpacserp', 'accepte_by', models.TextField(blank=True, db_column='AccepteBy', null=True)),
                migrations.AddField('tblpacserp', 'activation_date', models.DateTimeField(blank=True, db_column='ActivationDate', null=True)),
                migrations.AddField('tblpacserp', 'razorpay_payment_link_id', models.CharField(blank=True, db_column='RazorpayPaymentLinkID', max_length=50, null=True, unique=True)),
                migrations.AddField('tblpacserp', 'razorpay_payment_id', models.CharField(blank=True, db_column='RazorpayPaymentID', max_length=50, null=True, unique=True)),
                migrations.AddField('tblpacserp', 'razorpay_reference_id', models.CharField(blank=True, db_column='RazorpayReferenceID', max_length=40, null=True, unique=True)),
                migrations.AddField('tblpacserp', 'razorpay_payment_status', models.CharField(blank=True, db_column='RazorpayPaymentStatus', max_length=20, null=True)),
            ],
        )
    ]
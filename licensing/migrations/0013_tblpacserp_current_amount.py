from django.db import migrations, models


def add_current_amount(apps, schema_editor):
    connection = schema_editor.connection
    table_name = 'tblPacsErp'
    if table_name not in connection.introspection.table_names():
        return
    with connection.cursor() as cursor:
        existing = {column.name for column in connection.introspection.get_table_description(cursor, table_name)}
        table = schema_editor.quote_name(table_name)
        column = schema_editor.quote_name('CurrentAmount')
        column_added = 'CurrentAmount' not in existing
        if column_added:
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} INT NULL DEFAULT 4500')
        amount = schema_editor.quote_name('Amount')
        payment = schema_editor.quote_name('PaymentStatus')
        where_clause = '' if column_added else f'WHERE {column} IS NULL OR {column} NOT IN (3500, 4500)'
        cursor.execute(
            f'UPDATE {table} SET {column} = CASE '
            f'WHEN COALESCE({amount}, 0) > 0 AND COALESCE({payment}, 0) > 0 '
            f'AND {amount} = {payment} THEN 3500 ELSE 4500 END {where_clause}'
        )


def remove_current_amount(apps, schema_editor):
    connection = schema_editor.connection
    table_name = 'tblPacsErp'
    if table_name not in connection.introspection.table_names():
        return
    with connection.cursor() as cursor:
        existing = {column.name for column in connection.introspection.get_table_description(cursor, table_name)}
        if 'CurrentAmount' in existing:
            cursor.execute(
                f'ALTER TABLE {schema_editor.quote_name(table_name)} '
                f'DROP COLUMN {schema_editor.quote_name("CurrentAmount")}'
            )


class Migration(migrations.Migration):
    dependencies = [('licensing', '0012_tblpacserp_activation_razorpay_fields')]
    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(add_current_amount, remove_current_amount)],
            state_operations=[
                migrations.AddField(
                    model_name='tblpacserp',
                    name='current_amount',
                    field=models.IntegerField(blank=True, db_column='CurrentAmount', default=4500, null=True),
                ),
            ],
        ),
    ]
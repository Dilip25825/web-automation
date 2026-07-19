from django.db import migrations


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('licensing', '0009_versioninfo_alter_perpous_options_perpous_id_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            sql='CREATE INDEX idx_userinfo_mobile ON userinfo (Mobile)',
            reverse_sql='DROP INDEX idx_userinfo_mobile ON userinfo',
        ),
        migrations.RunSQL(
            sql='CREATE INDEX idx_userinfo_operator_mobile ON userinfo (OperatorMobile)',
            reverse_sql='DROP INDEX idx_userinfo_operator_mobile ON userinfo',
        ),
        migrations.RunSQL(
            sql='CREATE INDEX idx_userinfo_utr_number ON userinfo (UtrNumber)',
            reverse_sql='DROP INDEX idx_userinfo_utr_number ON userinfo',
        ),
    ]

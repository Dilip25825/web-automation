from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('licensing', '0015_erp_api_client_token_device_hash'),
    ]

    operations = [
        migrations.AlterField(
            model_name='erpapiclienttoken',
            name='operator_mobile',
            field=models.CharField(db_index=True, max_length=10),
        ),
        migrations.AddConstraint(
            model_name='erpapiclienttoken',
            constraint=models.UniqueConstraint(
                fields=('operator_mobile', 'device_hash'),
                name='uniq_erp_token_mobile_device',
            ),
        ),
    ]

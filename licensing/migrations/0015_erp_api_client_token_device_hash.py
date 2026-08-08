from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('licensing', '0014_erp_api_client_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='erpapiclienttoken',
            name='device_hash',
            field=models.CharField(blank=True, editable=False, max_length=64),
        ),
    ]
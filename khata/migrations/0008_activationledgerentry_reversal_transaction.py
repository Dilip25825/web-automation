import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('khata', '0007_activationledgerentry_activationledgermapping')]

    operations = [
        migrations.AddField(
            model_name='activationledgerentry',
            name='reversal_transaction',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='activation_reversal', to='khata.transaction'),
        ),
    ]
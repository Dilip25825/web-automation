import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('khata', '0006_transaction_attachment_drive_id_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivationLedgerMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('accepted_user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='accepted_activation_ledgers', to=settings.AUTH_USER_MODEL)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activation_user_mappings', to='khata.customer')),
                ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='activation_ledger_mappings', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='ActivationLedgerEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activation_token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('source_type', models.CharField(choices=[('USERINFO', 'UserInfo'), ('PACS_ERP', 'PACS ERP')], max_length=20)),
                ('source_record_id', models.PositiveBigIntegerField()),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('accepted_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='assigned_activation_ledger_entries', to=settings.AUTH_USER_MODEL)),
                ('activated_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='created_activation_ledger_entries', to=settings.AUTH_USER_MODEL)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='activation_ledger_entries', to='khata.customer')),
                ('transaction', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='activation_entry', to='khata.transaction')),
            ],
        ),
        migrations.AddConstraint(
            model_name='activationledgermapping',
            constraint=models.UniqueConstraint(fields=('owner', 'accepted_user'), name='unique_activation_ledger_user_mapping'),
        ),
        migrations.AddIndex(
            model_name='activationledgerentry',
            index=models.Index(fields=['source_type', 'source_record_id'], name='khata_activ_source__918027_idx'),
        ),
    ]
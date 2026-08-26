from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('licensing', '0016_erp_api_client_token_multi_device')]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterModelOptions(
                    name='perpous',
                    options={
                        'managed': False,
                        'verbose_name': 'Perpous',
                        'verbose_name_plural': 'Perpous',
                    },
                ),
                migrations.RemoveField(model_name='perpous', name='id'),
                migrations.AlterField(
                    model_name='perpous',
                    name='ID',
                    field=models.AutoField(db_column='ID', primary_key=True, serialize=False),
                ),
                migrations.AlterField(
                    model_name='perpous',
                    name='forWhy',
                    field=models.CharField(blank=True, db_column='forWhy', max_length=30, null=True, verbose_name='Purpose'),
                ),
            ],
        ),
    ]

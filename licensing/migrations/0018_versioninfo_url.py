from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('licensing', '0017_correct_perpous_model_state')]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    'ALTER TABLE `VersionInfo` ADD COLUMN IF NOT EXISTS `url` TEXT NULL',
                    migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='versioninfo',
                    name='url',
                    field=models.TextField(blank=True, db_column='url', null=True, verbose_name='Google Drive folder URL'),
                ),
            ],
        ),
    ]

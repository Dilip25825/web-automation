from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('onedownload', '0004_downloadlink_categories_and_required'),
    ]

    operations = [
        migrations.DeleteModel(name='DownloadLink'),
        migrations.DeleteModel(name='Category'),
    ]
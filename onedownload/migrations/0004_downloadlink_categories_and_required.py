from django.db import migrations, models


def copy_categories_and_mark_required(apps, schema_editor):
    Category = apps.get_model('onedownload', 'Category')
    DownloadLink = apps.get_model('onedownload', 'DownloadLink')
    general, _ = Category.objects.get_or_create(name='General')
    all_categories = list(Category.objects.all())

    for link in DownloadLink.objects.all():
        category = Category.objects.filter(name=link.category).first() or general
        if link.name == 'Web Automation Prerequisites Pack v1.49':
            link.is_required = True
            link.save(update_fields=['is_required'])
            link.categories.add(*all_categories)
        else:
            link.categories.add(category)


class Migration(migrations.Migration):
    dependencies = [
        ('onedownload', '0003_category_alter_downloadlink_category'),
    ]

    operations = [
        migrations.AddField(
            model_name='downloadlink',
            name='categories',
            field=models.ManyToManyField(blank=True, related_name='download_links', to='onedownload.category'),
        ),
        migrations.AddField(
            model_name='downloadlink',
            name='is_required',
            field=models.BooleanField(default=False, help_text='Show this file first and include it with every software category.'),
        ),
        migrations.AlterModelOptions(
            name='downloadlink',
            options={'ordering': ['-is_required', 'name']},
        ),
        migrations.RunPython(copy_categories_and_mark_required, migrations.RunPython.noop),
    ]

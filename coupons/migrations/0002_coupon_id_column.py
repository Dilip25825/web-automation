from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('coupons', '0001_initial')]
    operations = [
        migrations.AlterField(
            model_name='coupon',
            name='id',
            field=models.BigAutoField(db_column='ID', primary_key=True, serialize=False),
        ),
    ]

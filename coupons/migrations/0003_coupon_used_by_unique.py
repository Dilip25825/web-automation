from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('coupons', '0002_coupon_id_column')]
    operations = [
        migrations.AlterField(
            model_name='coupon',
            name='used_by',
            field=models.CharField(blank=True, db_column='UsedBy', max_length=100, null=True, unique=True),
        ),
    ]

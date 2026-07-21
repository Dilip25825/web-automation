from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='Coupon',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('coupon_code', models.CharField(db_column='CouponCode', max_length=32, unique=True)),
                ('discount_amount', models.PositiveIntegerField(db_column='DiscountAmount')),
                ('status', models.BooleanField(db_column='Status', default=True)),
                ('used_by', models.CharField(blank=True, db_column='UsedBy', max_length=100, null=True)),
                ('remark', models.TextField(blank=True, db_column='Remark', null=True)),
            ],
            options={'db_table': 'coupons_coupon', 'ordering': ['-id']},
        ),
    ]


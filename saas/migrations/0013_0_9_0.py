# Generated by Django 2.2.12 on 2020-05-24 22:23

from django.db import migrations, models
import django.db.models.deletion
import django_countries.fields


class Migration(migrations.Migration):

    dependencies = [
        ('saas', '0012_0_8_3'),
    ]

    operations = [
        migrations.RenameField(
            model_name='coupon',
            old_name='percent',
            new_name='discount_value',
        ),
        migrations.AddField(
            model_name='coupon',
            name='discount_type',
            field=models.PositiveSmallIntegerField(choices=[(1, 'Percentage'), (2, 'Currency')], default=1),
        ),
        migrations.RemoveField(
            model_name='plan',
            name='advance_discount',
        ),
        migrations.CreateModel(
            name='AdvanceDiscount',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('discount_type', models.PositiveSmallIntegerField(choices=[(1, 'Percentage'), (2, 'Currency'), (3, 'Period')], default=1)),
                ('discount_value', models.PositiveIntegerField(default=0, help_text='Amount of the discount')),
                ('length', models.PositiveSmallIntegerField(default=1, help_text='Contract length associated with the period (defaults to 1)')),
                ('plan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='advance_discounts', to='saas.Plan')),
            ],
        ),
    ]

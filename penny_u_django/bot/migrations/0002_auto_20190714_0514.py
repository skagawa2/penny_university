# Generated by Django 2.2.3 on 2019-07-14 05:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bot', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='real_name',
            field=models.CharField(default=None, max_length=100),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='user',
            name='user_name',
            field=models.CharField(default=None, max_length=100),
            preserve_default=False,
        ),
    ]

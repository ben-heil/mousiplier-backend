# Generated by Django 2.2.5 on 2019-11-12 19:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analyze', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='experiment',
            name='samples_info',
            field=models.TextField(default=''),
        ),
    ]

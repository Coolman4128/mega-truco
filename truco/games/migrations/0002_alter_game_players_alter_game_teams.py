# Generated by Django 5.0.6 on 2024-07-16 18:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('games', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='game',
            name='players',
            field=models.JSONField(default=dict, null=True),
        ),
        migrations.AlterField(
            model_name='game',
            name='teams',
            field=models.JSONField(default=dict, null=True),
        ),
    ]
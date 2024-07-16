# Generated by Django 5.0.6 on 2024-07-16 18:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('games', '0002_alter_game_players_alter_game_teams'),
    ]

    operations = [
        migrations.AddField(
            model_name='game',
            name='state',
            field=models.CharField(default='lobby', max_length=255),
        ),
        migrations.AlterField(
            model_name='board',
            name='cardsPlayed',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name='game',
            name='players',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name='game',
            name='teams',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name='player',
            name='hand',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

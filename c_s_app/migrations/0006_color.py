# Generated by Django 2.2.8 on 2020-03-27 09:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('c_s_app', '0005_feedback'),
    ]

    operations = [
        migrations.CreateModel(
            name='Color',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=32)),
            ],
        ),
    ]

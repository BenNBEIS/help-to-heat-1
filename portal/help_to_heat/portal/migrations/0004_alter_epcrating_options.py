# Generated by Django 3.2.19 on 2023-05-29 18:16

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0003_referral_session_id"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="epcrating",
            options={"ordering": ["created_at"]},
        ),
    ]

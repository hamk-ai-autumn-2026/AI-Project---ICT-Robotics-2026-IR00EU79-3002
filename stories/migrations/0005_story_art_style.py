from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stories", "0004_story_library_visibility"),
    ]

    operations = [
        migrations.AddField(
            model_name="story",
            name="art_style",
            field=models.CharField(
                choices=[
                    ("watercolor", "Warm watercolor"),
                    ("pencil", "Pencil illustration"),
                    ("anime", "Semi-realistic anime"),
                    ("3d-animation", "Polished 3D animation"),
                ],
                default="watercolor",
                max_length=20,
            ),
        ),
    ]

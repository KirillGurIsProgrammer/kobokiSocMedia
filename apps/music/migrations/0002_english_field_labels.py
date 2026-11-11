import apps.core.validators
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("music", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="album",
            name="title",
            field=models.CharField(max_length=100, verbose_name="Title"),
        ),
        migrations.AlterField(
            model_name="album",
            name="cover",
            field=models.ImageField(
                blank=True,
                upload_to="covers/",
                validators=[apps.core.validators.validate_image],
                verbose_name="Cover",
            ),
        ),
        migrations.AlterField(
            model_name="track",
            name="title",
            field=models.CharField(max_length=100, verbose_name="Title"),
        ),
        migrations.AlterField(
            model_name="track",
            name="artist",
            field=models.CharField(max_length=100, verbose_name="Artist"),
        ),
        migrations.AlterField(
            model_name="track",
            name="audio_file",
            field=models.FileField(
                upload_to="tracks/",
                validators=[apps.core.validators.validate_audio],
                verbose_name="Audio file",
            ),
        ),
        migrations.AlterField(
            model_name="review",
            name="rating",
            field=models.PositiveSmallIntegerField(
                validators=[
                    MinValueValidator(1),
                    MaxValueValidator(5),
                ],
                verbose_name="Rating",
            ),
        ),
        migrations.AlterField(
            model_name="review",
            name="text",
            field=models.TextField(blank=True, max_length=1000, verbose_name="Review"),
        ),
    ]

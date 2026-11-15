from django.db import migrations


def restore_track_column(apps, schema_editor):
    Post = apps.get_model("feed", "Post")
    track_field = Post._meta.get_field("track")
    table_name = Post._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        columns = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(
                cursor, table_name
            )
        }

    if track_field.column not in columns:
        schema_editor.add_field(Post, track_field)


class Migration(migrations.Migration):
    dependencies = [
        ("feed", "0004_alter_post_track_artist_alter_post_track_title_and_more"),
    ]

    operations = [
        migrations.RunPython(restore_track_column, migrations.RunPython.noop),
    ]

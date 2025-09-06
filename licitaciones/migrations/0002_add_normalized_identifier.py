from django.db import migrations, models


def normalize_identifiers(apps, schema_editor):
    Tender = apps.get_model('licitaciones', 'Tender')
    for t in Tender.objects.all():
        if t.identifier:
            t.normalized_identifier = t.identifier.replace('-', '')
            t.save(update_fields=['normalized_identifier'])


class Migration(migrations.Migration):

    dependencies = [
        ('licitaciones', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='tender',
            name='normalized_identifier',
            field=models.CharField(blank=True, db_index=True, max_length=128),
        ),
        migrations.RunPython(normalize_identifiers, reverse_code=migrations.RunPython.noop),
    ]



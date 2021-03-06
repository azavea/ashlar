# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ashlar', '0008_auto_20150429_1313'),
    ]

    operations = [
        migrations.AlterField(
            model_name='itemschema',
            name='next_version',
            field=models.OneToOneField(related_name='previous_version', null=True, editable=False, to='ashlar.ItemSchema'),
        ),
        migrations.AlterField(
            model_name='recordschema',
            name='next_version',
            field=models.OneToOneField(related_name='previous_version', null=True, editable=False, to='ashlar.RecordSchema'),
        ),
    ]

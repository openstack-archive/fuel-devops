# -*- coding: utf-8 -*-
# flake8: noqa
from south.db import db
from south.v2 import SchemaMigration


class Migration(SchemaMigration):
    def forwards(self, orm):
        # Removing unique constraint on 'Network', field ['ip_network']
        db.delete_unique(u'devops_network', ['ip_network'])

    def backwards(self, orm):
        # Adding unique constraint on 'Network', field ['ip_network']
        db.create_unique(u'devops_network', ['ip_network'])

    complete_apps = ['devops']

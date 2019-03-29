# -*- coding: utf-8 -*-
# flake8: noqa
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration


class Migration(SchemaMigration):
    def forwards(self, orm):
        # Adding field 'Environment.created'
        db.add_column('devops_environment', 'created',
                      self.gf('django.db.models.fields.DateTimeField')(
                          default=datetime.datetime.utcnow,
                          auto_now_add=True, blank=True), keep_default=False)

        # Adding field 'Node.created'
        db.add_column('devops_node', 'created',
                      self.gf('django.db.models.fields.DateTimeField')(
                          default=datetime.datetime.utcnow,
                          auto_now_add=True, blank=True), keep_default=False)

        # Adding field 'Volume.created'
        db.add_column('devops_volume', 'created',
                      self.gf('django.db.models.fields.DateTimeField')(
                          default=datetime.datetime.utcnow,
                          auto_now_add=True, blank=True), keep_default=False)

        # Adding field 'Network.created'
        db.add_column('devops_network', 'created',
                      self.gf('django.db.models.fields.DateTimeField')(
                          default=datetime.datetime.utcnow,
                          auto_now_add=True, blank=True), keep_default=False)

    def backwards(self, orm):
        # Deleting field 'Environment.created'
        db.delete_column('devops_environment', 'created')

        # Deleting field 'Node.created'
        db.delete_column('devops_node', 'created')

        # Deleting field 'Volume.created'
        db.delete_column('devops_volume', 'created')

        # Deleting field 'Network.created'
        db.delete_column('devops_network', 'created')

    models = {
        u'devops.address': {
            'Meta': {'object_name': 'Address'},
            u'id': (
                'django.db.models.fields.AutoField', [],
                {'primary_key': 'True'}),
            'interface': ('django.db.models.fields.related.ForeignKey', [],
                          {'to': u"orm['devops.Interface']"}),
            'ip_address': ('django.db.models.fields.GenericIPAddressField', [],
                           {'max_length': '39'})
        },
        u'devops.diskdevice': {
            'Meta': {'object_name': 'DiskDevice'},
            'bus': ('django.db.models.fields.CharField',
                    [], {'max_length': '255'}
                    ),
            'device': ('django.db.models.fields.CharField', [],
                       {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [],
                    {'primary_key': 'True'}),
            'node': ('django.db.models.fields.related.ForeignKey', [],
                     {'to': u"orm['devops.Node']"}),
            'target_dev': ('django.db.models.fields.CharField', [],
                           {'max_length': '255'}),
            'type': ('django.db.models.fields.CharField', [],
                     {'max_length': '255'}),
            'volume': ('django.db.models.fields.related.ForeignKey', [],
                       {'to': u"orm['devops.Volume']", 'null': 'True'})
        },
        u'devops.environment': {
            'Meta': {'object_name': 'Environment'},
            'created': ('django.db.models.fields.DateTimeField', [],
                        {'default': 'datetime.datetime.utcnow',
                         'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [],
                    {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [],
                     {'unique': 'True', 'max_length': '255'})
        },
        u'devops.interface': {
            'Meta': {'object_name': 'Interface'},
            u'id': ('django.db.models.fields.AutoField', [],
                    {'primary_key': 'True'}),
            'mac_address': ('django.db.models.fields.CharField', [],
                            {'unique': 'True', 'max_length': '255'}),
            'model': ('django.db.models.fields.CharField', [],
                      {'max_length': '255'}),
            'network': ('django.db.models.fields.related.ForeignKey', [],
                        {'to': u"orm['devops.Network']"}),
            'node': ('django.db.models.fields.related.ForeignKey', [],
                     {'to': u"orm['devops.Node']"}),
            'type': ('django.db.models.fields.CharField', [],
                     {'max_length': '255'})
        },
        u'devops.network': {
            'Meta': {'unique_together': "(('name', 'environment'),)",
                     'object_name': 'Network'},
            'created': ('django.db.models.fields.DateTimeField', [],
                        {'default': 'datetime.datetime.utcnow',
                         'auto_now_add': 'True', 'blank': 'True'}),
            'environment': ('django.db.models.fields.related.ForeignKey', [],
                            {'to': u"orm['devops.Environment']",
                             'null': 'True'}),
            'forward': ('django.db.models.fields.CharField', [],
                        {'max_length': '255', 'null': 'True'}),
            'has_dhcp_server': ('django.db.models.fields.BooleanField', [],
                                {}),
            'has_pxe_server': ('django.db.models.fields.BooleanField', [], {}),
            'has_reserved_ips': ('django.db.models.fields.BooleanField', [],
                                 {'default': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [],
                    {'primary_key': 'True'}),
            'ip_network': ('django.db.models.fields.CharField', [],
                           {'unique': 'True', 'max_length': '255'}),
            'name': ('django.db.models.fields.CharField', [],
                     {'max_length': '255'}),
            'tftp_root_dir': ('django.db.models.fields.CharField', [],
                              {'max_length': '255'}),
            'uuid': ('django.db.models.fields.CharField', [],
                     {'max_length': '255'})
        },
        u'devops.node': {
            'Meta': {'unique_together': "(('name', 'environment'),)",
                     'object_name': 'Node'},
            'architecture': ('django.db.models.fields.CharField', [],
                             {'max_length': '255'}),
            'boot': ('django.db.models.fields.CharField', [],
                     {'default': "'[]'", 'max_length': '255'}),
            'created': ('django.db.models.fields.DateTimeField', [],
                        {'default': 'datetime.datetime.utcnow',
                         'auto_now_add': 'True', 'blank': 'True'}),
            'environment': ('django.db.models.fields.related.ForeignKey', [],
                            {'to': u"orm['devops.Environment']",
                             'null': 'True'}),
            'enable_bootmenu': ('django.db.models.fields.BooleanField', [],
                                {'default': 'True'}),
            'has_vnc': ('django.db.models.fields.BooleanField', [],
                        {'default': 'True'}),
            'hypervisor': ('django.db.models.fields.CharField', [],
                           {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [],
                    {'primary_key': 'True'}),
            'memory': ('django.db.models.fields.IntegerField', [],
                       {'default': '1024'}),
            'metadata': ('django.db.models.fields.CharField', [],
                         {'max_length': '255', 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [],
                     {'max_length': '255'}),
            'os_type': ('django.db.models.fields.CharField', [],
                        {'max_length': '255'}),
            'role': ('django.db.models.fields.CharField', [],
                     {'max_length': '255', 'null': 'True'}),
            'uuid': ('django.db.models.fields.CharField', [],
                     {'max_length': '255'}),
            'vcpu': ('django.db.models.fields.PositiveSmallIntegerField', [],
                     {'default': '1'})
        },
        u'devops.volume': {
            'Meta': {'unique_together': "(('name', 'environment'),)",
                     'object_name': 'Volume'},
            'backing_store': ('django.db.models.fields.related.ForeignKey', [],
                              {'to': u"orm['devops.Volume']", 'null': 'True'}),
            'capacity': ('django.db.models.fields.BigIntegerField', [], {}),
            'created': ('django.db.models.fields.DateTimeField', [],
                        {'default': 'datetime.datetime.utcnow',
                         'auto_now_add': 'True', 'blank': 'True'}),
            'environment': ('django.db.models.fields.related.ForeignKey', [],
                            {'to': u"orm['devops.Environment']",
                             'null': 'True'}),
            'format': ('django.db.models.fields.CharField', [],
                       {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [],
                    {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [],
                     {'max_length': '255'}),
            'uuid': ('django.db.models.fields.CharField', [],
                     {'max_length': '255'})
        }
    }

    complete_apps = ['devops']

# -*- coding: utf-8 -*-
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):
    def forwards(self, orm):
        # Adding model 'Environment'
        db.create_table(u'devops_environment', (
            (u'id',
             self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name', self.gf('django.db.models.fields.CharField')(
                unique=True,
                max_length=255)),
        ))
        db.send_create_signal(u'devops', ['Environment'])

        # Adding model 'Network'
        db.create_table(u'devops_network', (
            (u'id',
             self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name',
             self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('uuid',
             self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('environment',
             self.gf('django.db.models.fields.related.ForeignKey')(
                 to=orm['devops.Environment'], null=True)),
            ('has_dhcp_server',
             self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('has_pxe_server',
             self.gf('django.db.models.fields.BooleanField')(default=False)),
            ('has_reserved_ips',
             self.gf('django.db.models.fields.BooleanField')(default=True)),
            ('tftp_root_dir',
             self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('forward',
             self.gf('django.db.models.fields.CharField')(max_length=255,
                                                          null=True)),
            ('ip_network',
             self.gf('django.db.models.fields.CharField')(unique=True,
                                                          max_length=255)),
        ))
        db.send_create_signal(u'devops', ['Network'])

        # Adding unique constraint on 'Network', fields ['name', 'environment']
        db.create_unique(u'devops_network', ['name', 'environment_id'])

        # Adding model 'Node'
        db.create_table(u'devops_node', (
            (u'id',
             self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name',
             self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('uuid',
             self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('environment',
             self.gf('django.db.models.fields.related.ForeignKey')(
                 to=orm['devops.Environment'], null=True)),
            ('hypervisor',
             self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('os_type',
             self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('architecture',
             self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('boot', self.gf('django.db.models.fields.CharField')(
                default='[]',
                max_length=255)),
            ('metadata',
             self.gf('django.db.models.fields.CharField')(max_length=255,
                                                          null=True)),
            ('role',
             self.gf('django.db.models.fields.CharField')(max_length=255,
                                                          null=True)),
            ('vcpu',
             self.gf('django.db.models.fields.PositiveSmallIntegerField')(
                 default=1)),
            ('memory',
             self.gf('django.db.models.fields.IntegerField')(default=1024)),
            ('has_vnc',
             self.gf('django.db.models.fields.BooleanField')(default=True)),
        ))
        db.send_create_signal(u'devops', ['Node'])

        # Adding unique constraint on 'Node', fields ['name', 'environment']
        db.create_unique(u'devops_node', ['name', 'environment_id'])

        # Adding model 'Volume'
        db.create_table(u'devops_volume', (
            (u'id',
             self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('name',
             self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('uuid',
             self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('environment',
             self.gf('django.db.models.fields.related.ForeignKey')(
                 to=orm['devops.Environment'], null=True)),
            ('capacity', self.gf('django.db.models.fields.BigIntegerField')()),
            ('backing_store',
             self.gf('django.db.models.fields.related.ForeignKey')(
                 to=orm['devops.Volume'], null=True)),
            ('format',
             self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal(u'devops', ['Volume'])

        # Adding unique constraint on 'Volume', fields ['name', 'environment']
        db.create_unique(u'devops_volume', ['name', 'environment_id'])

        # Adding model 'DiskDevice'
        db.create_table(u'devops_diskdevice', (
            (u'id',
             self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('device',
             self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('type',
             self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('bus',
             self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('target_dev',
             self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('node', self.gf('django.db.models.fields.related.ForeignKey')(
                to=orm['devops.Node'])),
            ('volume', self.gf('django.db.models.fields.related.ForeignKey')(
                to=orm['devops.Volume'], null=True)),
        ))
        db.send_create_signal(u'devops', ['DiskDevice'])

        # Adding model 'Interface'
        db.create_table(u'devops_interface', (
            (u'id',
             self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('mac_address',
             self.gf('django.db.models.fields.CharField')(unique=True,
                                                          max_length=255)),
            ('network', self.gf('django.db.models.fields.related.ForeignKey')(
                to=orm['devops.Network'])),
            ('node', self.gf('django.db.models.fields.related.ForeignKey')(
                to=orm['devops.Node'])),
            ('type',
             self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('model',
             self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal(u'devops', ['Interface'])

        # Adding model 'Address'
        db.create_table(u'devops_address', (
            (u'id',
             self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('ip_address',
             self.gf('django.db.models.fields.GenericIPAddressField')(
                 max_length=39)),
            ('interface',
             self.gf('django.db.models.fields.related.ForeignKey')(
                 to=orm['devops.Interface'])),
        ))
        db.send_create_signal(u'devops', ['Address'])

    def backwards(self, orm):
        # Removing unique constraint on 'Volume', fields [
        #   'name', 'environment']
        db.delete_unique(u'devops_volume', ['name', 'environment_id'])

        # Removing unique constraint on 'Node', fields ['name', 'environment']
        db.delete_unique(u'devops_node', ['name', 'environment_id'])

        # Removing unique constraint on 'Network', fields [
        #   'name', 'environment']
        db.delete_unique(u'devops_network', ['name', 'environment_id'])

        # Deleting model 'Environment'
        db.delete_table(u'devops_environment')

        # Deleting model 'Network'
        db.delete_table(u'devops_network')

        # Deleting model 'Node'
        db.delete_table(u'devops_node')

        # Deleting model 'Volume'
        db.delete_table(u'devops_volume')

        # Deleting model 'DiskDevice'
        db.delete_table(u'devops_diskdevice')

        # Deleting model 'Interface'
        db.delete_table(u'devops_interface')

        # Deleting model 'Address'
        db.delete_table(u'devops_address')

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
            'bus': (
                'django.db.models.fields.CharField', [],
                {'max_length': '255'}),
            'device': (
                'django.db.models.fields.CharField', [],
                {'max_length': '255'}),
            u'id': (
                'django.db.models.fields.AutoField', [],
                {'primary_key': 'True'}),
            'node': ('django.db.models.fields.related.ForeignKey', [],
                     {'to': u"orm['devops.Node']"}),
            'target_dev': (
                'django.db.models.fields.CharField', [],
                {'max_length': '255'}),
            'type': (
                'django.db.models.fields.CharField', [],
                {'max_length': '255'}),
            'volume': ('django.db.models.fields.related.ForeignKey', [],
                       {'to': u"orm['devops.Volume']", 'null': 'True'})
        },
        u'devops.environment': {
            'Meta': {'object_name': 'Environment'},
            u'id': (
                'django.db.models.fields.AutoField', [],
                {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [],
                     {'unique': 'True', 'max_length': '255'})
        },
        u'devops.interface': {
            'Meta': {'object_name': 'Interface'},
            u'id': (
                'django.db.models.fields.AutoField', [],
                {'primary_key': 'True'}),
            'mac_address': ('django.db.models.fields.CharField', [],
                            {'unique': 'True', 'max_length': '255'}),
            'model': (
                'django.db.models.fields.CharField', [],
                {'max_length': '255'}),
            'network': ('django.db.models.fields.related.ForeignKey', [],
                        {'to': u"orm['devops.Network']"}),
            'node': ('django.db.models.fields.related.ForeignKey', [],
                     {'to': u"orm['devops.Node']"}),
            'type': (
                'django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        u'devops.network': {
            'Meta': {'unique_together': "(('name', 'environment'),)",
                     'object_name': 'Network'},
            'environment': ('django.db.models.fields.related.ForeignKey', [],
                            {'to': u"orm['devops.Environment']",
                             'null': 'True'}),
            'forward': ('django.db.models.fields.CharField', [],
                        {'max_length': '255', 'null': 'True'}),
            'has_dhcp_server': (
                'django.db.models.fields.BooleanField', [],
                {'default': 'False'}),
            'has_pxe_server': (
                'django.db.models.fields.BooleanField', [],
                {'default': 'False'}),
            'has_reserved_ips': (
                'django.db.models.fields.BooleanField', [],
                {'default': 'True'}),
            u'id': (
                'django.db.models.fields.AutoField', [],
                {'primary_key': 'True'}),
            'ip_network': ('django.db.models.fields.CharField', [],
                           {'unique': 'True', 'max_length': '255'}),
            'name': (
                'django.db.models.fields.CharField', [],
                {'max_length': '255'}),
            'tftp_root_dir': (
                'django.db.models.fields.CharField', [],
                {'max_length': '255'}),
            'uuid': (
                'django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        u'devops.node': {
            'Meta': {'unique_together': "(('name', 'environment'),)",
                     'object_name': 'Node'},
            'architecture': (
                'django.db.models.fields.CharField', [],
                {'max_length': '255'}),
            'boot': ('django.db.models.fields.CharField', [],
                     {'default': "'[]'", 'max_length': '255'}),
            'environment': ('django.db.models.fields.related.ForeignKey', [],
                            {'to': u"orm['devops.Environment']",
                             'null': 'True'}),
            'has_vnc': (
                'django.db.models.fields.BooleanField', [],
                {'default': 'True'}),
            'hypervisor': (
                'django.db.models.fields.CharField', [],
                {'max_length': '255'}),
            u'id': (
                'django.db.models.fields.AutoField', [],
                {'primary_key': 'True'}),
            'memory': (
                'django.db.models.fields.IntegerField', [],
                {'default': '1024'}),
            'metadata': ('django.db.models.fields.CharField', [],
                         {'max_length': '255', 'null': 'True'}),
            'name': (
                'django.db.models.fields.CharField', [],
                {'max_length': '255'}),
            'os_type': (
                'django.db.models.fields.CharField', [],
                {'max_length': '255'}),
            'role': ('django.db.models.fields.CharField', [],
                     {'max_length': '255', 'null': 'True'}),
            'uuid': (
                'django.db.models.fields.CharField', [],
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
            'environment': ('django.db.models.fields.related.ForeignKey', [],
                            {'to': u"orm['devops.Environment']",
                             'null': 'True'}),
            'format': (
                'django.db.models.fields.CharField', [],
                {'max_length': '255'}),
            u'id': (
                'django.db.models.fields.AutoField', [],
                {'primary_key': 'True'}),
            'name': (
                'django.db.models.fields.CharField', [],
                {'max_length': '255'}),
            'uuid': (
                'django.db.models.fields.CharField', [], {'max_length': '255'})
        }
    }

    complete_apps = ['devops']

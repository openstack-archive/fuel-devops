# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        # Removing unique constraint on 'Volume', fields ['name', 'environment']
        db.delete_unique(u'devops_volume', ['name', 'environment_id'])

        # Removing unique constraint on 'Node', fields ['name', 'environment']
        db.delete_unique(u'devops_node', ['name', 'environment_id'])

        # Removing unique constraint on 'Network', fields ['name', 'environment']
        db.delete_unique(u'devops_network', ['name', 'environment_id'])

        # Deleting model 'Network'
        db.delete_table(u'devops_network')

        # Adding model 'Group'
        db.create_table('devops_group', (
            ('created', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.utcnow, auto_now_add=True, blank=True)),
            ('environment', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['devops.Environment'], null=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('driver', self.gf('django.db.models.fields.related.OneToOneField')(to=orm['devops.Driver'], unique=True, primary_key=True)),
        ))
        db.send_create_signal('devops', ['Group'])

        # Adding model 'Address_Pool'
        db.create_table('devops_address_pool', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.utcnow, auto_now_add=True, blank=True)),
            ('params', self.gf('jsonfield.fields.JSONField')(default={})),
            ('environment', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['devops.Environment'])),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('net', self.gf('django.db.models.fields.CharField')(unique=True, max_length=255)),
        ))
        db.send_create_signal('devops', ['Address_Pool'])

        # Adding unique constraint on 'Address_Pool', fields ['name', 'environment']
        db.create_unique('devops_address_pool', ['name', 'environment_id'])

        # Adding model 'L2_Network_Device'
        db.create_table('devops_l2_network_device', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.utcnow, auto_now_add=True, blank=True)),
            ('params', self.gf('jsonfield.fields.JSONField')(default={})),
            ('group', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['devops.Group'], null=True)),
            ('address_pool', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['devops.Address_Pool'])),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal('devops', ['L2_Network_Device'])

        # Adding model 'Driver'
        db.create_table('devops_driver', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.utcnow, auto_now_add=True, blank=True)),
            ('params', self.gf('jsonfield.fields.JSONField')(default={})),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=512)),
        ))
        db.send_create_signal('devops', ['Driver'])

        # Adding model 'NetworkPool'
        db.create_table('devops_network_pool', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.utcnow, auto_now_add=True, blank=True)),
            ('group', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['devops.Group'], null=True)),
            ('address_pool', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['devops.Address_Pool'])),
#            ('group', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['devops.Address_Pool'], null=True)),
#            ('address_pool', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['devops.Environment'], null=True)),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
        ))
        db.send_create_signal('devops', ['NetworkPool'])

        # Adding model 'Network_Config'
        db.create_table('devops_network_config', (
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('label', self.gf('django.db.models.fields.CharField')(max_length=255, null=False)),
            ('node', self.gf('django.db.models.fields.related.ForeignKey')(
                to=orm['devops.Node'])),
            ('networks', self.gf('jsonfield.fields.JSONField')(default=[])),
            ('aggregation', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('parents', self.gf('jsonfield.fields.JSONField')(default=[])),
        ))
        db.send_create_signal('devops', ['Network_Config'])

        # Deleting field 'Interface.network'
        db.delete_column(u'devops_interface', 'network_id')

        # Adding field 'Interface.l2_network_device'
        db.add_column('devops_interface', 'l2_network_device',
                      self.gf('django.db.models.fields.related.ForeignKey')(to=orm['devops.L2_Network_Device'], null=True),
                      keep_default=False)

        # Adding field 'Interface.label'
        db.add_column('devops_interface', 'label',
                      self.gf('django.db.models.fields.CharField')(max_length=255, null=True),
                      keep_default=False)

        # Deleting field 'Node.uuid'
        db.delete_column(u'devops_node', 'uuid')

        # Deleting field 'Node.has_vnc'
        db.delete_column(u'devops_node', 'has_vnc')

        # Deleting field 'Node.vcpu'
        db.delete_column(u'devops_node', 'vcpu')

        # Deleting field 'Node.hypervisor'
        db.delete_column(u'devops_node', 'hypervisor')

        # Deleting field 'Node.boot'
        db.delete_column(u'devops_node', 'boot')

        # Deleting field 'Node.environment'
        db.delete_column(u'devops_node', 'environment_id')

        # Deleting field 'Node.architecture'
        db.delete_column(u'devops_node', 'architecture')

        # Deleting field 'Node.memory'
        db.delete_column(u'devops_node', 'memory')

        # Deleting field 'Node.os_type'
        db.delete_column(u'devops_node', 'os_type')

        # Deleting field 'Node.metadata'
        db.delete_column(u'devops_node', 'metadata')

        # Adding field 'Node.params'
        db.add_column('devops_node', 'params',
                      self.gf('jsonfield.fields.JSONField')(default={}),
                      keep_default=False)

        # Adding field 'Node.group'
        db.add_column('devops_node', 'group',
                      self.gf('django.db.models.fields.related.ForeignKey')(to=orm['devops.Group'], null=True),
                      keep_default=False)

        # Adding unique constraint on 'Node', fields ['name', 'group']
        db.create_unique('devops_node', ['name', 'group_id'])

        # Deleting field 'Volume.environment'
        db.delete_column(u'devops_volume', 'environment_id')

        # Deleting field 'Volume.capacity'
        db.delete_column(u'devops_volume', 'capacity')

        # Deleting field 'Volume.format'
        db.delete_column(u'devops_volume', 'format')

        # Deleting field 'Volume.uuid'
        db.delete_column(u'devops_volume', 'uuid')

        # Adding field 'Volume.params'
        db.add_column('devops_volume', 'params',
                      self.gf('jsonfield.fields.JSONField')(default={}),
                      keep_default=False)

        # Adding field 'Volume.node'
        db.add_column('devops_volume', 'node',
                      self.gf('django.db.models.fields.related.ForeignKey')(to=orm['devops.Node'], null=True),
                      keep_default=False)

        # Adding unique constraint on 'Volume', fields ['name', 'node']
        db.create_unique('devops_volume', ['name', 'node_id'])


        # Changing field 'Address.interface'
        db.alter_column('devops_address', 'interface_id', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['devops.Interface'], null=True))

    def backwards(self, orm):
        # Removing unique constraint on 'Volume', fields ['name', 'group']
        db.delete_unique('devops_volume', ['name', 'group_id'])

        # Removing unique constraint on 'Node', fields ['name', 'group']
        db.delete_unique('devops_node', ['name', 'group_id'])

        # Removing unique constraint on 'Address_Pool', fields ['name', 'environment']
        db.delete_unique('devops_address_pool', ['name', 'environment_id'])

        # Adding model 'Network'
        db.create_table(u'devops_network', (
            ('ip_network', self.gf('django.db.models.fields.CharField')(max_length=255, unique=True)),
            ('has_reserved_ips', self.gf('django.db.models.fields.BooleanField')(default=True)),
            (u'id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('uuid', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('has_pxe_server', self.gf('django.db.models.fields.BooleanField')()),
            ('name', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('created', self.gf('django.db.models.fields.DateTimeField')(default=datetime.datetime.utcnow, auto_now_add=True, blank=True)),
            ('environment', self.gf('django.db.models.fields.related.ForeignKey')(to=orm['devops.Environment'], null=True)),
            ('tftp_root_dir', self.gf('django.db.models.fields.CharField')(max_length=255)),
            ('forward', self.gf('django.db.models.fields.CharField')(max_length=255, null=True)),
            ('has_dhcp_server', self.gf('django.db.models.fields.BooleanField')()),
        ))
        db.send_create_signal(u'devops', ['Network'])

        # Adding unique constraint on 'Network', fields ['name', 'environment']
        db.create_unique(u'devops_network', ['name', 'environment_id'])

        # Deleting model 'Group'
        db.delete_table('devops_group')

        # Deleting model 'Address_Pool'
        db.delete_table('devops_address_pool')

        # Deleting model 'L2_Network_Device'
        db.delete_table('devops_l2_network_device')

        # Deleting model 'Driver'
        db.delete_table('devops_driver')

        # Deleting model 'NetworkPool'
        db.delete_table('devops_network_pool')

        # Deleting model 'Network_Config'
        db.delete_table('devops_network_config')

        # Adding field 'Interface.network'
        db.add_column(u'devops_interface', 'network',
                      self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['devops.Network']),
                      keep_default=False)

        # Deleting field 'Interface.l2_network_device'
        db.delete_column('devops_interface', 'l2_network_device_id')

        # Deleting field 'Interface.label'
        db.delete_column('devops_interface', 'label')

        # Adding field 'Node.uuid'
        db.add_column(u'devops_node', 'uuid',
                      self.gf('django.db.models.fields.CharField')(default=None, max_length=255),
                      keep_default=False)

        # Adding field 'Node.has_vnc'
        db.add_column(u'devops_node', 'has_vnc',
                      self.gf('django.db.models.fields.BooleanField')(default=True),
                      keep_default=False)

        # Adding field 'Node.vcpu'
        db.add_column(u'devops_node', 'vcpu',
                      self.gf('django.db.models.fields.PositiveSmallIntegerField')(default=1),
                      keep_default=False)

        # Adding field 'Node.hypervisor'
        db.add_column(u'devops_node', 'hypervisor',
                      self.gf('django.db.models.fields.CharField')(default=None, max_length=255),
                      keep_default=False)

        # Adding field 'Node.boot'
        db.add_column(u'devops_node', 'boot',
                      self.gf('django.db.models.fields.CharField')(default='[]', max_length=255),
                      keep_default=False)

        # Adding field 'Node.environment'
        db.add_column(u'devops_node', 'environment',
                      self.gf('django.db.models.fields.related.ForeignKey')(to=orm['devops.Environment'], null=True),
                      keep_default=False)

        # Adding field 'Node.architecture'
        db.add_column(u'devops_node', 'architecture',
                      self.gf('django.db.models.fields.CharField')(default=None, max_length=255),
                      keep_default=False)

        # Adding field 'Node.memory'
        db.add_column(u'devops_node', 'memory',
                      self.gf('django.db.models.fields.IntegerField')(default=1024),
                      keep_default=False)

        # Adding field 'Node.os_type'
        db.add_column(u'devops_node', 'os_type',
                      self.gf('django.db.models.fields.CharField')(default=None, max_length=255),
                      keep_default=False)

        # Adding field 'Node.metadata'
        db.add_column(u'devops_node', 'metadata',
                      self.gf('django.db.models.fields.CharField')(max_length=255, null=True),
                      keep_default=False)

        # Deleting field 'Node.params'
        db.delete_column('devops_node', 'params')

        # Deleting field 'Node.group'
        db.delete_column('devops_node', 'group_id')

        # Adding unique constraint on 'Node', fields ['name', 'environment']
        db.create_unique(u'devops_node', ['name', 'environment_id'])

        # Adding field 'Volume.environment'
        db.add_column(u'devops_volume', 'environment',
                      self.gf('django.db.models.fields.related.ForeignKey')(to=orm['devops.Environment'], null=True),
                      keep_default=False)

        # Adding field 'Volume.capacity'
        db.add_column(u'devops_volume', 'capacity',
                      self.gf('django.db.models.fields.BigIntegerField')(default=None),
                      keep_default=False)

        # Adding field 'Volume.format'
        db.add_column(u'devops_volume', 'format',
                      self.gf('django.db.models.fields.CharField')(default=None, max_length=255),
                      keep_default=False)

        # Adding field 'Volume.uuid'
        db.add_column(u'devops_volume', 'uuid',
                      self.gf('django.db.models.fields.CharField')(default=None, max_length=255),
                      keep_default=False)

        # Deleting field 'Volume.params'
        db.delete_column('devops_volume', 'params')

        # Deleting field 'Volume.group'
        db.delete_column('devops_volume', 'group_id')

        # Adding unique constraint on 'Volume', fields ['name', 'environment']
        db.create_unique(u'devops_volume', ['name', 'environment_id'])


        # Changing field 'Address.interface'
        db.alter_column('devops_address', 'interface_id', self.gf('django.db.models.fields.related.ForeignKey')(default=None, to=orm['devops.Interface']))

    models = {
        'devops.address': {
            'Meta': {'object_name': 'Address'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'interface': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['devops.Interface']", 'null': 'True'}),
            'ip_address': ('django.db.models.fields.GenericIPAddressField', [], {'max_length': '39'})
        },
        'devops.address_pool': {
            'Meta': {'unique_together': "(('name', 'environment'),)", 'object_name': 'Address_Pool', 'db_table': "'devops_address_pool'"},
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow', 'auto_now_add': 'True', 'blank': 'True'}),
            'environment': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['devops.Environment']"}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'net': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'params': ('jsonfield.fields.JSONField', [], {'default': '{}'})
        },
        'devops.diskdevice': {
            'Meta': {'object_name': 'DiskDevice'},
            'bus': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'device': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'node': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['devops.Node']"}),
            'target_dev': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'volume': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['devops.Volume']", 'null': 'True'})
        },
        'devops.driver': {
            'Meta': {'object_name': 'Driver'},
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow', 'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '512'}),
            'params': ('jsonfield.fields.JSONField', [], {'default': '{}'})
        },
        'devops.environment': {
            'Meta': {'object_name': 'Environment'},
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow', 'auto_now_add': 'True', 'blank': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'})
        },
        'devops.group': {
            'Meta': {'object_name': 'Group'},
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow', 'auto_now_add': 'True', 'blank': 'True'}),
            'driver': ('django.db.models.fields.related.OneToOneField', [], {'to': "orm['devops.Driver']", 'unique': 'True', 'primary_key': 'True'}),
            'environment': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['devops.Environment']", 'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'devops.interface': {
            'Meta': {'object_name': 'Interface'},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'l2_network_device': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['devops.L2_Network_Device']", 'null': 'True'}),
            'label': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'}),
            'mac_address': ('django.db.models.fields.CharField', [], {'unique': 'True', 'max_length': '255'}),
            'model': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'node': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['devops.Node']"}),
            'type': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'devops.network_config': {
            'Meta': {'object_name': 'Network_Config', 'db_table': "'devops_network_config'"},
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'label': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'False'}),
            'node': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['devops.Node']"}),
            'aggregation': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'False'}),
            'networks': ('jsonfield.fields.JSONField', [], {'default': '[]'}),
            'parents': ('jsonfield.fields.JSONField', [], {'default': '[]'}),
        },
        'devops.l2_network_device': {
            'Meta': {'object_name': 'L2_Network_Device', 'db_table': "'devops_l2_network_device'"},
            'address_pool': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['devops.Address_Pool']"}),
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow', 'auto_now_add': 'True', 'blank': 'True'}),
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['devops.Group']", 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'params': ('jsonfield.fields.JSONField', [], {'default': '{}'})
        },
        'devops.networkpool': {
            'Meta': {'object_name': 'NetworkPool', 'db_table': "'devops_network_pool'"},
            'address_pool': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['devops.Environment']", 'null': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow', 'auto_now_add': 'True', 'blank': 'True'}),
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['devops.Address_Pool']", 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'})
        },
        'devops.node': {
            'Meta': {'unique_together': "(('name', 'group'),)", 'object_name': 'Node'},
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow', 'auto_now_add': 'True', 'blank': 'True'}),
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['devops.Group']", 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'params': ('jsonfield.fields.JSONField', [], {'default': '{}'}),
            'role': ('django.db.models.fields.CharField', [], {'max_length': '255', 'null': 'True'})
        },
        'devops.volume': {
            'Meta': {'unique_together': "(('name', 'group'),)", 'object_name': 'Volume'},
            'backing_store': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['devops.Volume']", 'null': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [], {'default': 'datetime.datetime.utcnow', 'auto_now_add': 'True', 'blank': 'True'}),
            'group': ('django.db.models.fields.related.ForeignKey', [], {'to': "orm['devops.Group']", 'null': 'True'}),
            u'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [], {'max_length': '255'}),
            'params': ('jsonfield.fields.JSONField', [], {'default': '{}'})
        }
    }

    complete_apps = ['devops']
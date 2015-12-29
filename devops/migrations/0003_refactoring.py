# -*- coding: utf-8 -*-
from south.utils import datetime_utils as datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models


class Migration(SchemaMigration):

    def forwards(self, orm):
        DateTimeField = self.gf('django.db.models.fields.DateTimeField')
        ForeignKey = self.gf('django.db.models.fields.related.ForeignKey')
        CharField = self.gf('django.db.models.fields.CharField')
        OneToOneField = self.gf(
            'django.db.models.fields.related.OneToOneField')
        AutoField = self.gf('django.db.models.fields.AutoField')
        JSONField = self.gf('jsonfield.fields.JSONField')

        # ------------------------ CREATE NEW MODELS -------------------------

        # Adding model 'Group'
        db.create_table('devops_group', (
            ('created', DateTimeField(default=datetime.datetime.utcnow,
                                      auto_now_add=True,
                                      blank=True)),
            ('environment', ForeignKey(to=orm['devops.Environment'],
                                       null=True)),
            ('name', CharField(max_length=255)),
            ('driver', OneToOneField(to=orm['devops.Driver'],
                                     unique=True,
                                     primary_key=True)),
        ))
        db.send_create_signal('devops', ['Group'])

        # Adding model 'AddressPool'
        db.create_table('devops_address_pool', (
            ('id', AutoField(primary_key=True)),
            ('created', DateTimeField(default=datetime.datetime.utcnow,
                                      auto_now_add=True,
                                      blank=True)),
            ('params', JSONField(default={})),
            ('environment', ForeignKey(to=orm['devops.Environment'])),
            ('name', CharField(max_length=255)),
            ('net', CharField(unique=True, max_length=255)),
        ))
        db.send_create_signal('devops', ['AddressPool'])

        # Adding unique constraint on 'AddressPool',
        # fields ['name', 'environment']
        db.create_unique('devops_address_pool', ['name', 'environment_id'])

        # Adding model 'L2NetworkDevice'
        db.create_table('devops_l2_network_device', (
            ('id', AutoField(primary_key=True)),
            ('created', DateTimeField(default=datetime.datetime.utcnow,
                                      auto_now_add=True,
                                      blank=True)),
            ('params', JSONField(default={})),
            ('group', ForeignKey(to=orm['devops.Group'], null=True)),
            ('address_pool', ForeignKey(to=orm['devops.AddressPool'])),
            ('name', CharField(max_length=255)),
        ))
        db.send_create_signal('devops', ['L2NetworkDevice'])

        # Adding model 'Driver'
        db.create_table('devops_driver', (
            ('id', AutoField(primary_key=True)),
            ('created', DateTimeField(default=datetime.datetime.utcnow,
                                      auto_now_add=True,
                                      blank=True)),
            ('params', JSONField(default={})),
            ('name', CharField(max_length=512)),
        ))
        db.send_create_signal('devops', ['Driver'])

        # Adding model 'NetworkPool'
        db.create_table('devops_network_pool', (
            ('id', AutoField(primary_key=True)),
            ('created', DateTimeField(default=datetime.datetime.utcnow,
                                      auto_now_add=True,
                                      blank=True)),
            ('group', ForeignKey(to=orm['devops.Group'], null=True)),
            ('address_pool', ForeignKey(to=orm['devops.AddressPool'])),
            ('name', CharField(max_length=255)),
        ))
        db.send_create_signal('devops', ['NetworkPool'])

        # Adding model 'NetworkConfig'
        db.create_table('devops_network_config', (
            ('id', AutoField(primary_key=True)),
            ('label', CharField(max_length=255)),
            ('node', ForeignKey(to=orm['devops.Node'])),
            ('networks', JSONField(default=[])),
            ('aggregation', CharField(max_length=255, null=True)),
            ('parents', JSONField(default=[])),
        ))
        db.send_create_signal('devops', ['NetworkConfig'])

        # Adding field 'Interface.l2_network_device'
        db.add_column('devops_interface',
                      'l2_network_device',
                      ForeignKey(to=orm['devops.L2NetworkDevice'],
                                 null=True),
                      keep_default=False)

        # Adding field 'Interface.label'
        db.add_column('devops_interface',
                      'label',
                      CharField(max_length=255, null=True),
                      keep_default=False)

        # Adding field 'Node.params'
        db.add_column('devops_node',
                      'params',
                      JSONField(default={}),
                      keep_default=False)

        # Adding field 'Node.group'
        db.add_column('devops_node',
                      'group',
                      ForeignKey(to=orm['devops.Group'], null=True),
                      keep_default=False)

        # Adding field 'Volume.node'
        db.add_column('devops_volume',
                      'node',
                      ForeignKey(to=orm['devops.Node'], null=True),
                      keep_default=False)

#        # Adding unique constraint on 'Volume', fields ['name', 'node']
#        db.create_unique('devops_volume', ['name', 'node_id'])

        # --------------------------- MIGRATE DATA ---------------------------

        # ------------------------ DELETE OLD MODELS -------------------------

        # Deleting field 'Interface.network'
        db.delete_column('devops_interface', 'network_id')

        # Deleting field 'Node.uuid'
        db.delete_column('devops_node', 'uuid')

        # Deleting field 'Node.has_vnc'
        db.delete_column('devops_node', 'has_vnc')

        # Deleting field 'Node.vcpu'
        db.delete_column('devops_node', 'vcpu')

        # Deleting field 'Node.hypervisor'
        db.delete_column('devops_node', 'hypervisor')

        # Deleting field 'Node.boot'
        db.delete_column('devops_node', 'boot')

        # Deleting field 'Node.environment'
        db.delete_column('devops_node', 'environment_id')

        # Deleting field 'Node.architecture'
        db.delete_column('devops_node', 'architecture')

        # Deleting field 'Node.memory'
        db.delete_column('devops_node', 'memory')

        # Deleting field 'Node.os_type'
        db.delete_column('devops_node', 'os_type')

        # Deleting field 'Node.metadata'
        db.delete_column('devops_node', 'metadata')

        # Adding unique constraint on 'Node', fields ['name', 'group']
        db.create_unique('devops_node', ['name', 'group_id'])

        # Deleting field 'Volume.environment'
        db.delete_column('devops_volume', 'environment_id')

        # Deleting field 'Volume.capacity'
        db.delete_column('devops_volume', 'capacity')

        # Deleting field 'Volume.format'
        db.delete_column('devops_volume', 'format')

        # Deleting field 'Volume.uuid'
        db.delete_column('devops_volume', 'uuid')

        # Adding field 'Volume.params'
        db.add_column('devops_volume', 'params',
                      self.gf('jsonfield.fields.JSONField')(default={}),
                      keep_default=False)

        # Changing field 'Address.interface'
        db.alter_column('devops_address',
                        'interface_id',
                        ForeignKey(to=orm['devops.Interface'], null=True))

        # Removing unique constraint on 'Volume',
        # fields ['name', 'environment']
        db.delete_unique('devops_volume', ['name', 'environment_id'])

        # Removing unique constraint on 'Node', fields ['name', 'environment']
        db.delete_unique('devops_node', ['name', 'environment_id'])

        # Removing unique constraint on 'Network',
        # fields ['name', 'environment']
        db.delete_unique('devops_network', ['name', 'environment_id'])

        # Deleting model 'Network'
        db.delete_table('devops_network')

    def backwards(self, orm):
        DateTimeField = self.gf('django.db.models.fields.DateTimeField')
        ForeignKey = self.gf('django.db.models.fields.related.ForeignKey')
        CharField = self.gf('django.db.models.fields.CharField')
        AutoField = self.gf('django.db.models.fields.AutoField')
        BooleanField = self.gf('django.db.models.fields.BooleanField')
        PositiveSmallIntegerField = self.gf(
            'django.db.models.fields.PositiveSmallIntegerField')
        IntegerField = self.gf('django.db.models.fields.IntegerField')
        BigIntegerField = self.gf('django.db.models.fields.BigIntegerField')

        # ------------------------ CREATE OLD MODELS -------------------------

        # Adding model 'Network'
        db.create_table('devops_network', (
            ('ip_network', CharField(max_length=255, unique=True)),
            ('has_reserved_ips', BooleanField(default=True)),
            ('id', AutoField(primary_key=True)),
            ('uuid', CharField(max_length=255)),
            ('has_pxe_server', BooleanField()),
            ('name', CharField(max_length=255)),
            ('created', DateTimeField(default=datetime.datetime.utcnow,
                                      auto_now_add=True,
                                      blank=True)),
            ('environment', ForeignKey(to=orm['devops.Environment'],
                                       null=True)),
            ('tftp_root_dir', CharField(max_length=255)),
            ('forward', CharField(max_length=255, null=True)),
            ('has_dhcp_server', BooleanField()),
        ))
        db.send_create_signal('devops', ['Network'])

        # Adding unique constraint on 'Network', fields ['name', 'environment']
        db.create_unique('devops_network', ['name', 'environment_id'])

        # Adding field 'Interface.network'
        db.add_column('devops_interface',
                      'network',
                      ForeignKey(default=None, null=True,
                                 to=orm['devops.Network']),
                      keep_default=False)

        # Adding field 'Node.uuid'
        db.add_column('devops_node', 'uuid',
                      CharField(default=None, max_length=255),
                      keep_default=False)

        # Adding field 'Node.has_vnc'
        db.add_column('devops_node', 'has_vnc',
                      BooleanField(default=True),
                      keep_default=False)

        # Adding field 'Node.vcpu'
        db.add_column('devops_node', 'vcpu',
                      PositiveSmallIntegerField(default=1),
                      keep_default=False)

        # Adding field 'Node.hypervisor'
        db.add_column('devops_node', 'hypervisor',
                      CharField(default=None, max_length=255),
                      keep_default=False)

        # Adding field 'Node.boot'
        db.add_column('devops_node', 'boot',
                      CharField(default='[]', max_length=255),
                      keep_default=False)

        # Adding field 'Node.environment'
        db.add_column('devops_node', 'environment',
                      ForeignKey(to=orm['devops.Environment'], null=True),
                      keep_default=False)

        # Adding field 'Node.architecture'
        db.add_column('devops_node', 'architecture',
                      CharField(default=None, max_length=255),
                      keep_default=False)

        # Adding field 'Node.memory'
        db.add_column('devops_node',
                      'memory',
                      IntegerField(default=1024),
                      keep_default=False)

        # Adding field 'Node.os_type'
        db.add_column('devops_node',
                      'os_type',
                      CharField(default=None, max_length=255),
                      keep_default=False)

        # Adding field 'Node.metadata'
        db.add_column('devops_node',
                      'metadata',
                      CharField(max_length=255, null=True),
                      keep_default=False)

        # Adding unique constraint on 'Node', fields ['name', 'environment']
        db.create_unique('devops_node', ['name', 'environment_id'])

        # Adding field 'Volume.environment'
        db.add_column('devops_volume',
                      'environment',
                      ForeignKey(to=orm['devops.Environment'], null=True),
                      keep_default=False)

        # Adding field 'Volume.capacity'
        db.add_column('devops_volume',
                      'capacity',
                      BigIntegerField(default=17284732847),
                      keep_default=False)

        # Adding field 'Volume.format'
        db.add_column('devops_volume',
                      'format',
                      CharField(default=None, max_length=255),
                      keep_default=False)

        # Adding field 'Volume.uuid'
        db.add_column('devops_volume',
                      'uuid',
                      CharField(default=None, max_length=255),
                      keep_default=False)

        # --------------------------- MIGRATE DATA ---------------------------

        # ------------------------ DELETE NEW MODELS -------------------------

        # Removing unique constraint on 'Volume', fields ['name', 'group']
        db.delete_unique('devops_volume', ['name', 'group_id'])

        # Removing unique constraint on 'Node', fields ['name', 'group']
        db.delete_unique('devops_node', ['name', 'group_id'])

        # Removing unique constraint on 'AddressPool',
        # fields ['name', 'environment']
        db.delete_unique('devops_address_pool', ['name', 'environment_id'])

        # Deleting model 'Group'
        db.delete_table('devops_group')

        # Deleting model 'AddressPool'
        db.delete_table('devops_address_pool')

        # Deleting model 'L2NetworkDevice'
        db.delete_table('devops_l2_network_device')

        # Deleting model 'Driver'
        db.delete_table('devops_driver')

        # Deleting model 'NetworkPool'
        db.delete_table('devops_network_pool')

        # Deleting model 'NetworkConfig'
        db.delete_table('devops_network_config')

        # Deleting field 'Interface.l2_network_device'
        db.delete_column('devops_interface', 'l2_network_device_id')

        # Deleting field 'Interface.label'
        db.delete_column('devops_interface', 'label')

        # Deleting field 'Node.params'
        db.delete_column('devops_node', 'params')

        # Deleting field 'Node.group'
        db.delete_column('devops_node', 'group_id')

        # Deleting field 'Volume.params'
        db.delete_column('devops_volume', 'params')

        # Adding unique constraint on 'Volume', fields ['name', 'environment']
        db.create_unique('devops_volume', ['name', 'environment_id'])

        # Changing field 'Address.interface'
        db.alter_column('devops_address',
                        'interface_id',
                        ForeignKey(default=None, to=orm['devops.Interface']))

#       # Removing unique constraint on 'Volume', fields ['name', 'node']
#       db.delete_unique('devops_volume', ['name', 'node_id'])

        # Deleting field 'Volume.node'
        db.delete_column('devops_volume', 'node_id')

    models = {
        'devops.address': {
            'Meta': {'object_name': 'Address'},
            'id': ('django.db.models.fields.AutoField', [],
                   {'primary_key': 'True'}),
            'interface': ('django.db.models.fields.related.ForeignKey', [],
                          {'to': "orm['devops.Interface']",
                           'null': 'True'}),
            'ip_address': ('django.db.models.fields.GenericIPAddressField',
                           [], {'max_length': '39'})
        },
        'devops.addresspool': {
            'Meta': {'unique_together': "(('name', 'environment'),)",
                     'object_name': 'AddressPool'},
            'created': ('django.db.models.fields.DateTimeField', [],
                        {'default': 'datetime.datetime.utcnow',
                         'auto_now_add': 'True',
                         'blank': 'True'}),
            'environment': ('django.db.models.fields.related.ForeignKey', [],
                            {'to': "orm['devops.Environment']"}),
            'id': ('django.db.models.fields.AutoField', [],
                   {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [],
                     {'max_length': '255'}),
            'net': ('django.db.models.fields.CharField', [],
                    {'unique': 'True', 'max_length': '255'}),
            'params': ('jsonfield.fields.JSONField', [], {'default': '{}'})
        },
        'devops.diskdevice': {
            'Meta': {'object_name': 'DiskDevice'},
            'bus': ('django.db.models.fields.CharField', [],
                    {'max_length': '255'}),
            'device': ('django.db.models.fields.CharField', [],
                       {'max_length': '255'}),
            'id': ('django.db.models.fields.AutoField', [],
                   {'primary_key': 'True'}),
            'node': ('django.db.models.fields.related.ForeignKey', [],
                     {'to': "orm['devops.Node']"}),
            'target_dev': ('django.db.models.fields.CharField', [],
                           {'max_length': '255'}),
            'type': ('django.db.models.fields.CharField', [],
                     {'max_length': '255'}),
            'volume': ('django.db.models.fields.related.ForeignKey', [],
                       {'to': "orm['devops.Volume']", 'null': 'True'})
        },
        'devops.driver': {
            'Meta': {'object_name': 'Driver'},
            'created': ('django.db.models.fields.DateTimeField', [],
                        {'default': 'datetime.datetime.utcnow',
                         'auto_now_add': 'True',
                         'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [],
                   {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [],
                     {'max_length': '512'}),
            'params': ('jsonfield.fields.JSONField', [],
                       {'default': '{}'})
        },
        'devops.environment': {
            'Meta': {'object_name': 'Environment'},
            'created': ('django.db.models.fields.DateTimeField', [],
                        {'default': 'datetime.datetime.utcnow',
                         'auto_now_add': 'True',
                         'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [],
                   {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [],
                     {'unique': 'True', 'max_length': '255'})
        },
        'devops.group': {
            'Meta': {'object_name': 'Group'},
            'created': ('django.db.models.fields.DateTimeField', [],
                        {'default': 'datetime.datetime.utcnow',
                         'auto_now_add': 'True',
                         'blank': 'True'}),
            'driver': ('django.db.models.fields.related.OneToOneField', [],
                       {'to': "orm['devops.Driver']",
                        'unique': 'True',
                        'primary_key': 'True'}),
            'environment': ('django.db.models.fields.related.ForeignKey', [],
                            {'to': "orm['devops.Environment']",
                             'null': 'True'}),
            'name': ('django.db.models.fields.CharField', [],
                     {'max_length': '255'})
        },
        'devops.interface': {
            'Meta': {'object_name': 'Interface'},
            'id': ('django.db.models.fields.AutoField', [],
                   {'primary_key': 'True'}),
            'l2_network_device': ('django.db.models.fields.related.ForeignKey',
                                  [], {'to': "orm['devops.L2NetworkDevice']",
                                       'null': 'True'}),
            'label': ('django.db.models.fields.CharField', [],
                      {'max_length': '255', 'null': 'True'}),
            'mac_address': ('django.db.models.fields.CharField', [],
                            {'unique': 'True', 'max_length': '255'}),
            'model': ('django.db.models.fields.CharField', [],
                      {'max_length': '255'}),
            'node': ('django.db.models.fields.related.ForeignKey', [],
                     {'to': "orm['devops.Node']"}),
            'type': ('django.db.models.fields.CharField', [],
                     {'max_length': '255'})
        },
        'devops.l2networkdevice': {
            'Meta': {'object_name': 'L2NetworkDevice'},
            'address_pool': ('django.db.models.fields.related.ForeignKey', [],
                             {'to': "orm['devops.AddressPool']"}),
            'created': ('django.db.models.fields.DateTimeField', [],
                        {'default': 'datetime.datetime.utcnow',
                         'auto_now_add': 'True',
                         'blank': 'True'}),
            'group': ('django.db.models.fields.related.ForeignKey', [],
                      {'to': "orm['devops.Group']", 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [],
                   {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [],
                     {'max_length': '255'}),
            'params': ('jsonfield.fields.JSONField', [], {'default': '{}'})
        },
        'devops.networkconfig': {
            'Meta': {'object_name': 'NetworkConfig'},
            'aggregation': ('django.db.models.fields.CharField', [],
                            {'max_length': '255', 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [],
                   {'primary_key': 'True'}),
            'label': ('django.db.models.fields.CharField', [],
                      {'max_length': '255'}),
            'networks': ('jsonfield.fields.JSONField', [], {'default': '[]'}),
            'node': ('django.db.models.fields.related.ForeignKey', [],
                     {'to': "orm['devops.Node']"}),
            'parents': ('jsonfield.fields.JSONField', [], {'default': '[]'})
        },
        'devops.networkpool': {
            'Meta': {'object_name': 'NetworkPool',
                     'db_table': "'devops_network_pool'"},
            'address_pool': ('django.db.models.fields.related.ForeignKey', [],
                             {'to': "orm['devops.AddressPool']",
                              'null': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [],
                        {'default': 'datetime.datetime.utcnow',
                         'auto_now_add': 'True',
                         'blank': 'True'}),
            'group': ('django.db.models.fields.related.ForeignKey', [],
                      {'to': "orm['devops.Group']", 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [],
                   {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [],
                     {'max_length': '255'})
        },
        'devops.node': {
            'Meta': {'unique_together': "(('name', 'group'),)",
                     'object_name': 'Node'},
            'created': ('django.db.models.fields.DateTimeField', [],
                        {'default': 'datetime.datetime.utcnow',
                         'auto_now_add': 'True',
                         'blank': 'True'}),
            'group': ('django.db.models.fields.related.ForeignKey', [],
                      {'to': "orm['devops.Group']", 'null': 'True'}),
            'id': ('django.db.models.fields.AutoField', [],
                   {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [],
                     {'max_length': '255'}),
            'params': ('jsonfield.fields.JSONField', [], {'default': '{}'}),
            'role': ('django.db.models.fields.CharField', [],
                     {'max_length': '255', 'null': 'True'})
        },
        'devops.volume': {
#            'Meta': {'unique_together': "(('name', 'node'),)",
            'Meta': {'object_name': 'Volume'},
            'backing_store': ('django.db.models.fields.related.ForeignKey', [],
                              {'to': "orm['devops.Volume']", 'null': 'True'}),
            'created': ('django.db.models.fields.DateTimeField', [],
                        {'default': 'datetime.datetime.utcnow',
                         'auto_now_add': 'True',
                         'blank': 'True'}),
            'id': ('django.db.models.fields.AutoField', [],
                   {'primary_key': 'True'}),
            'name': ('django.db.models.fields.CharField', [],
                     {'max_length': '255'}),
            'node': ('django.db.models.fields.related.ForeignKey', [],
                     {'to': "orm['devops.Node']", 'null': 'True'}),
            'params': ('jsonfield.fields.JSONField', [], {'default': '{}'})
        }
    }

    complete_apps = ['devops']

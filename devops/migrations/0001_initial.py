# -*- coding: utf-8 -*-
# flake8: noqa
# pylint: skip-file
from __future__ import unicode_literals

from django.db import migrations, models
import datetime
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Address',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('ip_address', models.GenericIPAddressField()),
            ],
            options={
                'db_table': 'devops_address',
            },
        ),
        migrations.CreateModel(
            name='AddressPool',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=datetime.datetime.utcnow)),
                ('params', jsonfield.fields.JSONField(default={})),
                ('name', models.CharField(max_length=255)),
                ('net', models.CharField(unique=True, max_length=255)),
            ],
            options={
                'db_table': 'devops_address_pool',
            },
        ),
        migrations.CreateModel(
            name='DiskDevice',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('device', models.CharField(choices=[('disk', 'disk'), ('cdrom', 'cdrom')], max_length=255)),
                ('type', models.CharField(choices=[('file', 'file')], max_length=255)),
                ('bus', models.CharField(choices=[('virtio', 'virtio')], max_length=255)),
                ('target_dev', models.CharField(max_length=255)),
            ],
            options={
                'db_table': 'devops_diskdevice',
            },
        ),
        migrations.CreateModel(
            name='Driver',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=datetime.datetime.utcnow)),
                ('params', jsonfield.fields.JSONField(default={})),
                ('name', models.CharField(max_length=512)),
            ],
            options={
                'db_table': 'devops_driver',
            },
        ),
        migrations.CreateModel(
            name='Environment',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=datetime.datetime.utcnow)),
                ('name', models.CharField(unique=True, max_length=255)),
            ],
            options={
                'db_table': 'devops_environment',
            },
        ),
        migrations.CreateModel(
            name='Interface',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('params', jsonfield.fields.JSONField(default={})),
                ('label', models.CharField(null=True, max_length=255)),
                ('mac_address', models.CharField(unique=True, max_length=255)),
                ('type', models.CharField(max_length=255)),
                ('model', models.CharField(choices=[('virtio', 'virtio'), ('e1000', 'e1000'), ('pcnet', 'pcnet'), ('rtl8139', 'rtl8139'), ('ne2k_pci', 'ne2k_pci')], max_length=255)),
            ],
            options={
                'db_table': 'devops_interface',
            },
        ),
        migrations.CreateModel(
            name='L2NetworkDevice',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=datetime.datetime.utcnow)),
                ('params', jsonfield.fields.JSONField(default={})),
                ('name', models.CharField(max_length=255)),
                ('address_pool', models.ForeignKey(null=True, to='devops.AddressPool')),
            ],
            options={
                'db_table': 'devops_l2_network_device',
            },
        ),
        migrations.CreateModel(
            name='NetworkConfig',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('label', models.CharField(max_length=255)),
                ('networks', jsonfield.fields.JSONField(default=[])),
                ('aggregation', models.CharField(null=True, max_length=255)),
                ('parents', jsonfield.fields.JSONField(default=[])),
            ],
            options={
                'db_table': 'devops_network_config',
            },
        ),
        migrations.CreateModel(
            name='NetworkPool',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=datetime.datetime.utcnow)),
                ('name', models.CharField(max_length=255)),
                ('address_pool', models.ForeignKey(null=True, to='devops.AddressPool')),
            ],
            options={
                'db_table': 'devops_network_pool',
            },
        ),
        migrations.CreateModel(
            name='Node',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=datetime.datetime.utcnow)),
                ('params', jsonfield.fields.JSONField(default={})),
                ('name', models.CharField(max_length=255)),
                ('role', models.CharField(null=True, max_length=255)),
            ],
            options={
                'db_table': 'devops_node',
            },
        ),
        migrations.CreateModel(
            name='Volume',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=datetime.datetime.utcnow)),
                ('params', jsonfield.fields.JSONField(default={})),
                ('name', models.CharField(max_length=255)),
                ('backing_store', models.ForeignKey(null=True, to='devops.Volume')),
                ('node', models.ForeignKey(null=True, to='devops.Node')),
            ],
            options={
                'db_table': 'devops_volume',
            },
        ),
        migrations.CreateModel(
            name='Group',
            fields=[
                ('created', models.DateTimeField(default=datetime.datetime.utcnow)),
                ('name', models.CharField(max_length=255)),
                ('driver', models.OneToOneField(serialize=False, primary_key=True, to='devops.Driver')),
                ('environment', models.ForeignKey(null=True, to='devops.Environment')),
            ],
            options={
                'db_table': 'devops_group',
            },
        ),
        migrations.AddField(
            model_name='networkconfig',
            name='node',
            field=models.ForeignKey(to='devops.Node'),
        ),
        migrations.AddField(
            model_name='interface',
            name='l2_network_device',
            field=models.ForeignKey(null=True, to='devops.L2NetworkDevice'),
        ),
        migrations.AddField(
            model_name='interface',
            name='node',
            field=models.ForeignKey(to='devops.Node'),
        ),
        migrations.AddField(
            model_name='diskdevice',
            name='node',
            field=models.ForeignKey(to='devops.Node'),
        ),
        migrations.AddField(
            model_name='diskdevice',
            name='volume',
            field=models.ForeignKey(null=True, to='devops.Volume'),
        ),
        migrations.AddField(
            model_name='addresspool',
            name='environment',
            field=models.ForeignKey(to='devops.Environment'),
        ),
        migrations.AddField(
            model_name='address',
            name='interface',
            field=models.ForeignKey(null=True, to='devops.Interface'),
        ),
        migrations.AlterUniqueTogether(
            name='volume',
            unique_together=set([('name', 'node')]),
        ),
        migrations.AddField(
            model_name='node',
            name='group',
            field=models.ForeignKey(null=True, to='devops.Group'),
        ),
        migrations.AddField(
            model_name='networkpool',
            name='group',
            field=models.ForeignKey(null=True, to='devops.Group'),
        ),
        migrations.AddField(
            model_name='l2networkdevice',
            name='group',
            field=models.ForeignKey(null=True, to='devops.Group'),
        ),
        migrations.AlterUniqueTogether(
            name='addresspool',
            unique_together=set([('name', 'environment')]),
        ),
        migrations.AlterUniqueTogether(
            name='node',
            unique_together=set([('name', 'group')]),
        ),
    ]

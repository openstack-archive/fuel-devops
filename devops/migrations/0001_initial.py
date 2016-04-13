# -*- coding: utf-8 -*-
# flake8: noqa
from __future__ import unicode_literals

from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Address',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('ip_address', models.GenericIPAddressField()),
            ],
            options={
                'db_table': 'devops_address',
            },
        ),
        migrations.CreateModel(
            name='DiskDevice',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('device', models.CharField(max_length=255, choices=[(b'disk', b'disk'), (b'cdrom', b'cdrom')])),
                ('type', models.CharField(max_length=255, choices=[(b'file', b'file')])),
                ('bus', models.CharField(max_length=255, choices=[(b'virtio', b'virtio'), (b'scsi', b'scsi')])),
                ('target_dev', models.CharField(max_length=255)),
            ],
            options={
                'db_table': 'devops_diskdevice',
            },
        ),
        migrations.CreateModel(
            name='Environment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
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
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('mac_address', models.CharField(unique=True, max_length=255)),
                ('type', models.CharField(max_length=255)),
                ('model', models.CharField(max_length=255, choices=[(b'virtio', b'virtio'), (b'e1000', b'e1000'), (b'pcnet', b'pcnet'), (b'rtl8139', b'rtl8139'), (b'ne2k_pci', b'ne2k_pci')])),
            ],
            options={
                'db_table': 'devops_interface',
            },
        ),
        migrations.CreateModel(
            name='Network',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=datetime.datetime.utcnow)),
                ('name', models.CharField(max_length=255)),
                ('uuid', models.CharField(max_length=255)),
                ('has_dhcp_server', models.BooleanField()),
                ('has_pxe_server', models.BooleanField()),
                ('has_reserved_ips', models.BooleanField(default=True)),
                ('tftp_root_dir', models.CharField(max_length=255)),
                ('forward', models.CharField(max_length=255, null=True, choices=[(b'nat', b'nat'), (b'route', b'route'), (b'bridge', b'bridge'), (b'private', b'private'), (b'vepa', b'vepa'), (b'passthrough', b'passthrough'), (b'hostdev', b'hostdev')])),
                ('ip_network', models.CharField(unique=True, max_length=255)),
                ('environment', models.ForeignKey(to='devops.Environment', null=True)),
            ],
            options={
                'db_table': 'devops_network',
            },
        ),
        migrations.CreateModel(
            name='Node',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=datetime.datetime.utcnow)),
                ('name', models.CharField(max_length=255)),
                ('uuid', models.CharField(max_length=255)),
                ('hypervisor', models.CharField(max_length=255, choices=[(b'kvm', b'kvm')])),
                ('os_type', models.CharField(max_length=255, choices=[(b'hvm', b'hvm')])),
                ('architecture', models.CharField(max_length=255, choices=[(b'x86_64', b'x86_64'), (b'i686', b'i686')])),
                ('boot', models.CharField(default=b'[]', max_length=255)),
                ('metadata', models.CharField(max_length=255, null=True)),
                ('role', models.CharField(max_length=255, null=True)),
                ('vcpu', models.PositiveSmallIntegerField(default=1)),
                ('memory', models.IntegerField(default=1024)),
                ('has_vnc', models.BooleanField(default=True)),
                ('environment', models.ForeignKey(to='devops.Environment', null=True)),
            ],
            options={
                'db_table': 'devops_node',
            },
        ),
        migrations.CreateModel(
            name='Volume',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', models.DateTimeField(default=datetime.datetime.utcnow)),
                ('name', models.CharField(max_length=255)),
                ('uuid', models.CharField(max_length=255)),
                ('capacity', models.BigIntegerField()),
                ('format', models.CharField(max_length=255)),
                ('backing_store', models.ForeignKey(to='devops.Volume', null=True)),
                ('environment', models.ForeignKey(to='devops.Environment', null=True)),
            ],
            options={
                'db_table': 'devops_volume',
            },
        ),
        migrations.AddField(
            model_name='interface',
            name='network',
            field=models.ForeignKey(to='devops.Network'),
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
            field=models.ForeignKey(to='devops.Volume', null=True),
        ),
        migrations.AddField(
            model_name='address',
            name='interface',
            field=models.ForeignKey(to='devops.Interface'),
        ),
        migrations.AlterUniqueTogether(
            name='volume',
            unique_together=set([('name', 'environment')]),
        ),
        migrations.AlterUniqueTogether(
            name='node',
            unique_together=set([('name', 'environment')]),
        ),
        migrations.AlterUniqueTogether(
            name='network',
            unique_together=set([('name', 'environment')]),
        ),
    ]

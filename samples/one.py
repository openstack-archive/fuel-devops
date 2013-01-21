import os
def one(manager):
    environment = manager.environment_create('test_env7')
    internal = manager.network_create(
        environment=environment, name='internal', pool=None)
    external = manager.network_create(
        environment=environment, name='external', pool=None)
    private = manager.network_create(
        environment=environment, name='private', pool=None)
    node = manager.node_create(name='test_node', environment=environment)
    manager.interface_create(node=node, network=internal)
    manager.interface_create(node=node, network=external)
    manager.interface_create(node=node, network=private)
    volume = manager.volume_get_predefined('/var/lib/libvirt/images/disk-135824657433.qcow2')
    v3 = manager.volume_create_child('test_vp895', backing_store=volume, environment=environment)
    v4 = manager.volume_create_child('test_vp896', backing_store=volume, environment=environment)
    manager.node_attach_volume(node=node, volume=v3)
    manager.node_attach_volume(node, v4)
    environment.define()
    environment.start()



if __name__ == '__main__':
    from devops.manager import Manager
    one(Manager())


.. _clsdiagram:

Diagrams
========

Database schema
***************

This diagram shows schema of database::

    +-----------------+      +----------------+
    |   Environment   |-----o|  Address pool  |-------------+
    +-----------------+      +----------------+             |
             |                       |                      |
             |                       o                      |
             |               +----------------+             |
             |               |  Network pool  |             |
             |               +----------------+             |
             |                       o                      |
             |                       |                      o
             |    +------------------+              +----------------+
             o    |                          +-----o|   L2 Network   |-------------+
    +-----------------+                      |      |     Device     |             |
    |      Group      |----------------------+      +----------------+             |
    +-----------------+                                                            o
             |    |                                 +----------------+      +-------------+     +---------------+
             |    +--------------------------------o|      Node      |-----o|  Interface  |----o|    Address    |
             |                                      +----------------+      +-------------+     +---------------+
             |                                          |   |   |
             |                       +------------------+   |   |           +-------------+
             |                       |                      |   +----------o|   Network   |
             |                       o                      o               | config (for |
    +-----------------+      +----------------+     +----------------+      | interfaces) |
    |     Driver      |      |     Volume     |----o|      Disk      |      +-------------+
    +-----------------+      +----------------+     +----------------+

    o-----o  - many to many relation
    ------o  - one to many relation
    -------  - one to one relation


Class Diagrams
**************

This diagram shows class hierarchy::

    +--------------------+
    | models.Environment |
    +--------------------+
      |
      |  +--------------------+
      +->| models.AddressPool |
      |  +--------------------+
      |
      |  +--------------------+
      +->| models.Group       |
         +--------------------+
           |
           |  +---------------------+
           +->| models.NetworkPool  |
           |  +---------------------+
           |
           |
           +-> driver.driver_name1.Driver(models.Driver)
           |
           +-> driver.driver_name1.L2NetworkDevice(models.L2NetworkDevice)
           |
           +-> driver.driver_name1.Node(models.Node)
           |   |
           |   +-> driver.driver_name1.Volume(models.Volume)
           |
           |
           +-> driver.driver_name2.Driver(models.Driver)
           |
           +-> driver.driver_name2.L2NetworkDevice(models.L2NetworkDevice)
           |
           +-> driver.driver_name2.Node(models.Node)
           |   |
           |   +-> driver.driver_name2.Volume(models.Volume)
           |
           |
           +-> driver.driver_name3.Driver(models.Driver)
           |
           +-> driver.driver_name3.L2NetworkDevice(models.L2NetworkDevice)
           |
           +-> driver.driver_name3.Node(models.Node)
               |
               +-> driver.driver_name3.Volume(models.Volume)


This diagram shows class hierarchy for Node::

  +-------------+
  | models.Node |
  +-------------+
     |
     +-> models.Volume
     |
     +-> models.Disk
     |
     +-> models.NetworkConfig
     |
     +-> models.Interface
         |
         +-> models.Address

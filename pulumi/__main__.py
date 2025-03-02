"""An AWS Python Pulumi program"""

import pulumi
import pulumi_aws as aws
import os
import json

config = pulumi.Config()

# ssh key must be generated separately and in .env in the current directory must be a definition for
# PUBLIC_SSH_KEY_PATH with the path to the public key
public_ssh_key_path = os.environ.get("PUBLIC_SSH_KEY_PATH")

if public_ssh_key_path is None:
    raise ValueError("PUBLIC_SSH_KEY_PATH must be defined in .env file")

ec2_config = config.require_object("ec2")

# instance type for the bastion host
bastion_instance_type = ec2_config["bastion_instance_type"]

# instance type for the cluster nodes

# instance type for the bastion host
bastion_instance_type = ec2_config["bastion_instance_type"]

# instance type for the cluster nodes
instance_type = ec2_config["instance_type"]

# user data for vpc instances
machine_image = ec2_config["ami"]


# return the list of availability zones
zones = config.require_object("availability_zones")

vpc = aws.ec2.Vpc(
    "nomad-cluster",
    cidr_block="10.0.0.0/16",
    enable_dns_support=True,
    enable_dns_hostnames=True,
    tags={"Name": "nomad-cluster"},
)

# public key for ec2 instances
ec2_key = aws.ec2.KeyPair(
    "nomad-cluster-key",
    public_key=open(public_ssh_key_path).read(),
    tags={"Name": "nomad-cluster-key"},
)

# internet gateway
internet_gateway = aws.ec2.InternetGateway(
    "nomad-cluster-gateway",
    vpc_id=vpc.id,
    tags={"Name": "nomad-cluster-gateway"},
)


# subnet creation: 
#   private subnet
#   public subnet
#   bastion subnet

# private subnet for the cluster nodes
private_subnet = aws.ec2.Subnet(
    "nomad-cluster-private",
    vpc_id=vpc.id,
    cidr_block="10.0.0.0/24",
    availability_zone=zones[0],
    tags={"Name": "nomad-cluster-private"},
)

# public subnet for the gateway services
public_subnet = aws.ec2.Subnet(
    "nomad-cluster-public",
    vpc_id=vpc.id,
    cidr_block="10.0.1.0/24",
    availability_zone=zones[1],
    map_public_ip_on_launch=True,
    tags={"Name": "nomad-cluster-public"},
)

# bastion subnet for the bastion host
bastion_subnet = aws.ec2.Subnet(
    "nomad-cluster-bastion",
    vpc_id=vpc.id,
    cidr_block="10.0.10.0/28", # 12 valid addresses
    availability_zone=zones[2],
    map_public_ip_on_launch=True,
    tags={"Name": "nomad-cluster-bastion"},
)


# route table for the public subnet
public_route_table = aws.ec2.RouteTable(
    "nomad-cluster-public-route-table",
    vpc_id=vpc.id,
    routes=[{"cidr_block": "0.0.0.0/0", "gateway_id": internet_gateway.id}],
    tags={"Name": "nomad-cluster-public-route-table"},
)

# associate the public route table with the public subnet
public_route_table_association = aws.ec2.RouteTableAssociation(
    "nomad-cluster-public-route-table-association",
    subnet_id=public_subnet.id,
    route_table_id=public_route_table.id
)

# route table for the bastion subnet
bastion_route_table = aws.ec2.RouteTable(
    "nomad-cluster-bastion-route-table",
    vpc_id=vpc.id,
    routes=[{"cidr_block": "0.0.0.0/0", "gateway_id": internet_gateway.id}],
    tags={"Name": "nomad-cluster-bastion-route-table"},
)

# associate the bastion route table with the bastion subnet
bastion_route_table_association = aws.ec2.RouteTableAssociation(
    "nomad-cluster-bastion-route-table-association",
    subnet_id=bastion_subnet.id,
    route_table_id=bastion_route_table.id
)


# elastic IP for the NAT gateway
elastic_ip = aws.ec2.Eip("nomad-cluster-nat-eip")

# NAT gateway for the private subnet
nat_gateway = aws.ec2.NatGateway(
    "nomad-cluster-nat-gateway",
    subnet_id=public_subnet.id,
    allocation_id=elastic_ip.id,
    tags={"Name": "nomad-cluster-nat-gateway"},
)


# route table for the private subnet
private_route_table = aws.ec2.RouteTable(
    "nomad-cluster-private-route-table",
    vpc_id=vpc.id,
    routes=[{"cidr_block": "0.0.0.0/0", "nat_gateway_id": nat_gateway.id}],
    tags={"Name": "nomad-cluster-private-route-table"},
)

# associate the private route table with the private subnet
private_route_table_association = aws.ec2.RouteTableAssociation(
    "nomad-cluster-private-route-table-association",
    subnet_id=private_subnet.id,
    route_table_id=private_route_table.id
)

# security group for the cluster nodes
ssh_security_group = aws.ec2.SecurityGroup(
    "nomad-ssh-sg",
    vpc_id=vpc.id,
    description="Group allows to communicate with the cluster nodes only through the bastion host",
    
    # incoming traffic rules
    ingress=[
        {
            "protocol": "tcp",
            "from_port": 22,
            "to_port": 22,
            "cidr_blocks": ["10.0.10.0/28"], 
            "description": "allow ssh from bastion host"
        },
    ],

    # outgoing traffic rules
    egress=[
        {
            "protocol": "-1",
            "from_port": 0,
            "to_port": 0,
            "cidr_blocks": ["0.0.0.0/0"]
        }
    ],
    tags={"Name": "nomad-ssh-sg"},
)

# consul servers security group
consul_security_group = aws.ec2.SecurityGroup("consul-sg",
    vpc_id=vpc_id,
    description="Security group for Consul cluster nodes",
    
    ingress=[
        # consul-to-consul
        {"protocol": "tcp", "from_port": 8300, "to_port": 8300, "cidr_blocks": ["10.0.0.0/16"], "description": "Raft protocol (leader election)"},
        {"protocol": "tcp", "from_port": 8301, "to_port": 8301, "cidr_blocks": ["10.0.0.0/16"], "description": "LAN Gossip (TCP)"},
        {"protocol": "udp", "from_port": 8301, "to_port": 8301, "cidr_blocks": ["10.0.0.0/16"], "description": "LAN Gossip (UDP)"},
        {"protocol": "tcp", "from_port": 8302, "to_port": 8302, "cidr_blocks": ["10.0.0.0/16"], "description": "WAN Gossip (TCP)"},
        {"protocol": "udp", "from_port": 8302, "to_port": 8302, "cidr_blocks": ["10.0.0.0/16"], "description": "WAN Gossip (UDP)"},
        # nomad-to-consul
        {"protocol": "tcp", "from_port": 8500, "to_port": 8500, "cidr_blocks": ["0.0.0.0/0"],  "security_groups": [nomad_security_group.id], "description": "Consul HTTP API/UI"},
        {"protocol": "tcp", "from_port": 8600, "to_port": 8600, "cidr_blocks": ["10.0.0.0/16"], "security_groups": [nomad_security_group.id], "description": "Consul DNS (TCP)"},
        {"protocol": "udp", "from_port": 8600, "to_port": 8600, "cidr_blocks": ["10.0.0.0/16"], "security_groups": [nomad_security_group.id], "description": "Consul DNS (UDP)"},
    ],
    
    egress=[
        {"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"], "description": "Allow all outbound traffic"}
    ],
    tags={"Name": "consul-sg"}
)

# nomad nodes security group
nomad_security_group = aws.ec2.SecurityGroup("nomad-sg",
    vpc_id=vpc_id,
    description="Security group for Nomad servers and clients",

    ingress=[
        {"protocol": "tcp", "from_port": 4646, "to_port": 4646, "cidr_blocks": ["0.0.0.0/0"], "description": "Nomad HTTP API"},
        {"protocol": "tcp", "from_port": 4647, "to_port": 4647, "cidr_blocks": ["10.0.0.0/16"], "description": "Nomad RPC"},
        {"protocol": "tcp", "from_port": 4648, "to_port": 4648, "cidr_blocks": ["10.0.0.0/16"], "description": "Nomad Gossip (TCP)"},
        {"protocol": "udp", "from_port": 4648, "to_port": 4648, "cidr_blocks": ["10.0.0.0/16"], "description": "Nomad Gossip (UDP)"},

        # nomad to consul
        {"protocol": "tcp", "from_port": 8500, "to_port": 8500, "security_groups": [consul_security_group.id], "description": "Nomad to Consul HTTP API"},
        {"protocol": "tcp", "from_port": 8600, "to_port": 8600, "security_groups": [consul_security_group.id], "description": "Nomad to Consul DNS (TCP)"},
        {"protocol": "udp", "from_port": 8600, "to_port": 8600, "security_groups": [consul_security_group.id], "description": "Nomad to Consul DNS (UDP)"},

    ],

    egress=[
        {"protocol": "-1", "from_port": 0, "to_port": 0, "cidr_blocks": ["0.0.0.0/0"], "description": "Allow all outbound traffic"}
    ],
    tags={"Name": "nomad-sg"}
)


# security group for the bastion host
bastion_security_group = aws.ec2.SecurityGroup(
    "nomad-bastion-sg",
    vpc_id=vpc.id,
    description="Group allows to communicate with the bastion host from anywhere",
    
    # incoming traffic rules
    ingress=[
        {
            "protocol": "tcp",
            "from_port": 22,
            "to_port": 22,
            "cidr_blocks": ["0.0.0.0/0"],
            "description": "allow ssh from anywhere"
        },
    ],
    
    # outgoing traffic rules
    egress=[
        {
            "protocol": "tcp",
            "from_port": 22,
            "to_port": 22,
            "cidr_blocks": ["10.0.0.0/24", "10.0.1.0/24"],
            "description": "allow ssh to the cluster nodes"
        },
        {
            "protocol": "-1",
            "from_port": 0,
            "to_port": 0,
            "cidr_blocks": ["0.0.0.0/0"]
        }
    ],
    tags={"Name": "nomad-bastion-sg"}
)

#bastion server name 
bastion_name = "nomad-bastion"

# create the bastion host
bastion_instance = aws.ec2.Instance(
    bastion_name,
    ami=machine_image,
    instance_type=instance_type,
    vpc_security_group_ids=[bastion_security_group.id],
    subnet_id=bastion_subnet.id,
    key_name=ec2_key.key_name,
    tags={"Name": "nomad-bastion"},
    user_data=f"""#!/bin/bash
                    yum update -y
                    yum install -y jq
                    yum install -y ansible
                    yum install -y python3
                    yum install -y python3-pip""",
)

pulumi.export("bastion_instance_public_ip", bastion_instance.public_ip)
# create the public instances
# the subnet is 10.0.0.4/24
private_instances_data = [ 
                            {
                              "private_ip": "10.0.0.4",
                              "type":"client",
                            },
                            {
                                "private_ip": "10.0.0.5",
                                "type": [ "server", "consul" ],
                            },
                            {
                                "private_ip": "10.0.0.6",
                                "type":"client",
                            },
                            {
                                "private_ip": "10.0.0.7",
                                "type": [ "server", "consul" ],
                            }
                        ]

# count of public instances
private_instances_count = len(private_instances_data)

pulumi.export("vpc_cidr", vpc.cidr_block)


# provision of private instances
for i in range(private_instances_count):
    server_name = f"nomad-{private_instances_data[i]["type"][0] if type(private_instances_data[i]["type"]) == type(list()) else private_instances_data[i]["type"]}-{i + 1}"

    security_groups = [ssh_security_group.id]
    
    if "consul" in private_instances_data[i]["type"]:
        security_groups.append(consul_security_group.id)

    if "nomad" in private_instances_data[i]["type"]:
        security_groups.append(nomad_security_group.id)

    private_instance = aws.ec2.Instance(
        resource_name=server_name,
        ami=machine_image,
        instance_type=instance_type,
        vpc_security_group_ids=security_groups,
        subnet_id=private_subnet.id,
        private_ip=private_instances_data[i]["private_ip"],
        key_name=ec2_key.key_name,
        tags={
            "Name": server_name, 
            "Role": "|".join(private_instances_data[i]["type"]) if type(private_instances_data[i]["type"]) == type(list()) else private_instances_data[i]["type"] 
            }
    )
    
    # private_instances_data[i]["id"] = private_instance.id
    private_instances_data[i]["name"] = server_name
    
    pulumi.export(f"private_instance_{i + 1}_private_ip", private_instance.private_ip)
    pulumi.export(f"private_instance_{i + 1}_public_ip", private_instance.public_ip)
    

# public instances
public_instances_data = [
                            {
                                "private_ip": "10.0.1.4",
                                "type":"haproxy",
                            },
                        ]

# count of public instances 
public_instances_count = len(public_instances_data)

# provision of public instances
for i in range(public_instances_count):
    server_name = f"nomad-{public_instances_data[i]["type"]}-{i + 1}"

    public_instance = aws.ec2.Instance(
        resource_name=server_name,
        ami=machine_image,
        instance_type=instance_type,
        vpc_security_group_ids=[ssh_security_group.id],
        subnet_id=public_subnet.id,
        private_ip=public_instances_data[i]["private_ip"],
        key_name=ec2_key.key_name,
        tags={
            "Name": server_name, 
            "Role": public_instances_data[i]["type"]
            }
    )

    
    # public_instances_data[i]["id"] = public_instance.id
    public_instances_data[i]["name"] = server_name
    
    try: 
        public_instance.public_ip.apply(lambda x: public_instances_data[i].update({"public_ip": str(x)}))
    except pulumi.Output:
        public_instances_data[i]["public_ip"] = None

    pulumi.export(f"public_instance_{i + 1}_private_ip", public_instance.private_ip)
    pulumi.export(f"public_instance_{i + 1}_private_ip", public_instance.private_ip)

# join lists of private and public instances 
instances_data = private_instances_data + public_instances_data + [ { 
                                                                     "type": "bastion", 
                                                                     "name": bastion_name } ]
    
with open("../ansible/inventory.json", "w") as f:
    json.dump(instances_data, f, indent=2)

# export the amoount of instances
pulumi.export("instances_count", private_instances_count + public_instances_count)

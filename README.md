# Nomad Cluster on AWS with Pulumi and Ansible

This repository provisions and configures a Nomad cluster on AWS using Pulumi for infrastructure provisioning and Ansible for configuration management. The setup includes Nomad, Consul, and HAProxy deployed on EC2 instances, with service discovery and load balancing configured for containerized workloads.

## Overview

- **Infrastructure Provisioning:**  
  Pulumi (TypeScript) is used to provision AWS resources (VPC, subnets, EC2 instances, etc.) required for the Nomad cluster.

- **Configuration Management:**  
  Ansible playbooks and roles configure the cluster nodes with:
  - Nomad server/client agents
  - Consul for service discovery and health checks
  - HAProxy as the external gateway/load balancer

- **Workload Scheduling:**  
  Nomad is used to schedule and manage Docker containers across the cluster. Nomad jobs are defined under the `nomad/jobs` directory.

## Repository Structure



# DockPulse 2.0 — AWS Infrastructure Architecture (Terraform)

This directory defines the Infrastructure as Code (IaC) configuration for deploying DockPulse 2.0 onto Amazon Web Services (AWS).

## Architecture Highlights
- **VPC**: Dedicated Virtual Private Cloud (`10.0.0.0/16`) across multiple availability zones.
- **Subnets**: Public subnets with Internet Gateway routing for external access.
- **Security Groups**: Strictly configured ingress for:
  - Port `5000`: DockPulse Web UI
  - Port `80`: Standard HTTP
  - Port `9090`: Prometheus Time-Series DB
  - Port `8089`: cAdvisor Container Telemetry
- **Compute Tier**: Prepared for either containerized EC2 node execution or AWS Elastic Kubernetes Service (EKS).

## Deployment Commands (When AWS credentials are provided)
```bash
# 1. Initialize providers
terraform init

# 2. Validate configuration
terraform validate

# 3. Plan deployment
terraform plan

# 4. Provision infrastructure (do not run without valid AWS account & credentials)
terraform apply
```

> **Note**: This configuration is prepared for cloud deployment. In the local demonstration environment, DockPulse runs locally on Docker Desktop and KIND.

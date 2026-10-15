output "vpc_id" {
  description = "The ID of the DockPulse VPC"
  value       = aws_vpc.dockpulse_vpc.id
}

output "security_group_id" {
  description = "Security Group ID for DockPulse ingress"
  value       = aws_security_group.dockpulse_sg.id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = [aws_subnet.public_subnet_a.id, aws_subnet.public_subnet_b.id]
}

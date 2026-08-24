output "repository_url" {
  value       = module.ecr.repository_url
  description = "The URL of the ECR repository"
}

output "route53_name_servers" {
  value       = module.route53.name_servers
  description = "Nameservers to configure at Namecheap for this domain"
}

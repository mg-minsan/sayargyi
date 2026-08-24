output "zone_id" {
  description = "The ID of the Route53 zone"
  value       = aws_route53_zone.main.zone_id
}

output "name_servers" {
  description = "Nameservers to configure at Namecheap for this domain"
  value       = aws_route53_zone.main.name_servers
}
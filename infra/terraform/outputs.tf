# CULTR Ventures — Terraform Outputs

output "tunnel_id" {
  description = "Cloudflare Tunnel ID"
  value       = cloudflare_tunnel.main.id
}

output "tunnel_token" {
  description = "Cloudflare Tunnel token for cloudflared"
  value       = cloudflare_tunnel.main.tunnel_token
  sensitive   = true
}

output "dns_records" {
  description = "Created DNS records"
  value = {
    root      = cloudflare_record.root.hostname
    www       = cloudflare_record.www.hostname
    api       = cloudflare_record.api.hostname
    knowledge = cloudflare_record.knowledge.hostname
  }
}

output "staging_ip" {
  description = "Staging server IP (if enabled)"
  value       = var.enable_staging ? hcloud_server.staging[0].ipv4_address : "N/A"
}

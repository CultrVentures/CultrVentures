# CULTR Ventures — Terraform Variables

variable "hcloud_token" {
  description = "Hetzner Cloud API token"
  type        = string
  sensitive   = true
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token with DNS and Tunnel permissions"
  type        = string
  sensitive   = true
}

variable "cloudflare_account_id" {
  description = "Cloudflare account ID"
  type        = string
}

variable "tunnel_secret" {
  description = "Secret for Cloudflare Tunnel authentication"
  type        = string
  sensitive   = true
}

variable "ssh_public_key" {
  description = "SSH public key for server access"
  type        = string
}

variable "allowed_ssh_ips" {
  description = "IP addresses allowed to SSH (CIDR notation)"
  type        = list(string)
  default     = ["0.0.0.0/0"]  # CHANGE THIS to your IP in production
}

variable "hetzner_location" {
  description = "Hetzner datacenter location"
  type        = string
  default     = "fsn1"  # Falkenstein (cheapest, good EU+US east latency)
}

variable "enable_staging" {
  description = "Whether to provision a staging VPS"
  type        = bool
  default     = false
}

# --- Dedicated Server IPs (set after manual provisioning) ---

variable "ax52_ip" {
  description = "Public IP of the AX52 compute node (set after ordering)"
  type        = string
  default     = ""
}

variable "gex44_ip" {
  description = "Public IP of the GEX44 GPU node (set after ordering)"
  type        = string
  default     = ""
}

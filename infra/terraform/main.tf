# CULTR Ventures — Terraform Main
# Provisions: Hetzner servers + Cloudflare DNS/tunnel

terraform {
  required_version = ">= 1.5"
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.45"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }

  backend "local" {
    path = "terraform.tfstate"
  }
}

# --- Providers ---

provider "hcloud" {
  token = var.hcloud_token
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

# --- SSH Key ---

resource "hcloud_ssh_key" "deploy" {
  name       = "cultr-deploy"
  public_key = var.ssh_public_key
}

# --- Private Network (AX52 ↔ GEX44) ---

resource "hcloud_network" "private" {
  name     = "cultr-private"
  ip_range = "10.0.0.0/24"
}

resource "hcloud_network_subnet" "compute" {
  network_id   = hcloud_network.private.id
  type         = "cloud"
  network_zone = "eu-central"
  ip_range     = "10.0.0.0/24"
}

# --- Firewall ---

resource "hcloud_firewall" "compute" {
  name = "cultr-compute"

  # SSH — restricted to your IP
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = var.allowed_ssh_ips
  }

  # ICMP (ping for monitoring)
  rule {
    direction  = "in"
    protocol   = "icmp"
    source_ips = ["0.0.0.0/0", "::/0"]
  }

  # All outbound (needed for cloudflared, Docker pulls, API calls)
  rule {
    direction       = "out"
    protocol        = "tcp"
    port            = "1-65535"
    destination_ips = ["0.0.0.0/0", "::/0"]
  }

  rule {
    direction       = "out"
    protocol        = "udp"
    port            = "1-65535"
    destination_ips = ["0.0.0.0/0", "::/0"]
  }
}

resource "hcloud_firewall" "gpu" {
  name = "cultr-gpu"

  # SSH — restricted to your IP
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = var.allowed_ssh_ips
  }

  # Private VLAN from AX52 only
  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "8080-8082"
    source_ips = ["10.0.0.0/24"]
  }

  # Outbound for Docker pulls and model downloads
  rule {
    direction       = "out"
    protocol        = "tcp"
    port            = "1-65535"
    destination_ips = ["0.0.0.0/0", "::/0"]
  }
}

# --- Note: Dedicated servers (AX52, GEX44) ---
# Hetzner dedicated servers are NOT managed by Terraform's hcloud provider.
# They must be ordered via Hetzner Robot API or web console.
# After provisioning, configure with Ansible.
#
# This Terraform config manages:
# - Cloudflare DNS records
# - Cloudflare Tunnel
# - Hetzner Cloud resources (optional staging VPS, firewalls, networks)
# - Hetzner Cloud floating IPs (if needed)

# --- Optional: Staging VPS ---

resource "hcloud_server" "staging" {
  count       = var.enable_staging ? 1 : 0
  name        = "cultr-staging"
  server_type = "cpx31"
  image       = "ubuntu-24.04"
  location    = var.hetzner_location
  ssh_keys    = [hcloud_ssh_key.deploy.id]
  firewall_ids = [hcloud_firewall.compute.id]

  labels = {
    environment = "staging"
    project     = "cultr-ventures"
  }
}

# --- Cloudflare Zone ---

data "cloudflare_zone" "main" {
  name = "cultrventures.com"
}

# --- Cloudflare Tunnel ---

resource "cloudflare_tunnel" "main" {
  account_id = var.cloudflare_account_id
  name       = "cultr-production"
  secret     = var.tunnel_secret
}

# --- DNS Records ---

resource "cloudflare_record" "root" {
  zone_id = data.cloudflare_zone.main.id
  name    = "@"
  content = "${cloudflare_tunnel.main.id}.cfargotunnel.com"
  type    = "CNAME"
  proxied = true
}

resource "cloudflare_record" "www" {
  zone_id = data.cloudflare_zone.main.id
  name    = "www"
  content = "cultrventures.com"
  type    = "CNAME"
  proxied = true
}

resource "cloudflare_record" "api" {
  zone_id = data.cloudflare_zone.main.id
  name    = "api"
  content = "${cloudflare_tunnel.main.id}.cfargotunnel.com"
  type    = "CNAME"
  proxied = true
}

resource "cloudflare_record" "knowledge" {
  zone_id = data.cloudflare_zone.main.id
  name    = "knowledge"
  content = "cultr-knowledge.pages.dev"
  type    = "CNAME"
  proxied = true
}

# --- Tunnel Config ---

resource "cloudflare_tunnel_config" "main" {
  account_id = var.cloudflare_account_id
  tunnel_id  = cloudflare_tunnel.main.id

  config {
    ingress_rule {
      hostname = "cultrventures.com"
      path     = "/api/*"
      service  = "http://localhost:8000"
    }

    ingress_rule {
      hostname = "cultrventures.com"
      path     = "/portal/*"
      service  = "http://localhost:4321"
    }

    ingress_rule {
      hostname = "api.cultrventures.com"
      service  = "http://localhost:8000"
    }

    # Catch-all (required)
    ingress_rule {
      service = "http_status:404"
    }
  }
}

# --- Cloudflare Page Rules ---

resource "cloudflare_page_rule" "cache_assets" {
  zone_id  = data.cloudflare_zone.main.id
  target   = "cultrventures.com/assets/*"
  priority = 1

  actions {
    cache_level       = "cache_everything"
    edge_cache_ttl    = 31536000  # 1 year
    browser_cache_ttl = 31536000
  }
}

resource "cloudflare_page_rule" "no_cache_api" {
  zone_id  = data.cloudflare_zone.main.id
  target   = "cultrventures.com/api/*"
  priority = 2

  actions {
    cache_level = "bypass"
  }
}

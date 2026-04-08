/**
 * CULTR Ventures — Rate Limiter Worker
 * Edge-based rate limiting using Cloudflare Workers KV / Durable Objects.
 *
 * Strategies:
 *   1. Sliding window per IP   (unauthenticated: 60 req/min)
 *   2. Sliding window per user (authenticated:  120 req/min)
 *   3. Burst protection        (any: 20 req/sec)
 *   4. Agent API tier          (agent endpoints: 30 req/min per agent)
 *
 * Environment bindings (wrangler.toml):
 *   RATE_LIMIT_KV  — KV namespace for counters
 */

export interface Env {
  RATE_LIMIT_KV: KVNamespace;
}

interface RateLimitConfig {
  maxRequests: number;
  windowSeconds: number;
}

// Tier definitions
const TIERS: Record<string, RateLimitConfig> = {
  unauthenticated: { maxRequests: 60, windowSeconds: 60 },
  authenticated: { maxRequests: 120, windowSeconds: 60 },
  agent_api: { maxRequests: 30, windowSeconds: 60 },
  burst: { maxRequests: 20, windowSeconds: 1 },
};

// Paths that get the stricter agent_api tier
const AGENT_PATHS = ["/api/v1/agents/", "/api/v1/mcp/", "/api/v1/acp/"];

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;

    // Skip rate limiting for health checks
    if (path === "/api/health") {
      return fetch(request);
    }

    const ip =
      request.headers.get("CF-Connecting-IP") ??
      request.headers.get("X-Forwarded-For")?.split(",")[0]?.trim() ??
      "unknown";
    const userId = request.headers.get("X-Cultr-User-Id");

    // --- Burst check (per IP, 1-second window) -------------------------
    const burstResult = await checkRateLimit(
      env.RATE_LIMIT_KV,
      `burst:${ip}`,
      TIERS.burst
    );
    if (!burstResult.allowed) {
      return rateLimitResponse(burstResult, "Burst limit exceeded");
    }

    // --- Tier-based check -----------------------------------------------
    const tier = getTier(path, userId);
    const key = userId ? `user:${userId}` : `ip:${ip}`;
    const tierResult = await checkRateLimit(
      env.RATE_LIMIT_KV,
      `${tier}:${key}`,
      TIERS[tier]
    );

    if (!tierResult.allowed) {
      return rateLimitResponse(tierResult, "Rate limit exceeded");
    }

    // --- Forward with rate limit headers --------------------------------
    const response = await fetch(request);
    const newResponse = new Response(response.body, response);
    newResponse.headers.set(
      "X-RateLimit-Limit",
      String(TIERS[tier].maxRequests)
    );
    newResponse.headers.set(
      "X-RateLimit-Remaining",
      String(tierResult.remaining)
    );
    newResponse.headers.set(
      "X-RateLimit-Reset",
      String(tierResult.resetAt)
    );
    return newResponse;
  },
};

// --- Sliding window rate limiter using KV --------------------------------

interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  resetAt: number;
}

async function checkRateLimit(
  kv: KVNamespace,
  key: string,
  config: RateLimitConfig
): Promise<RateLimitResult> {
  const now = Math.floor(Date.now() / 1000);
  const windowStart = now - config.windowSeconds;
  const kvKey = `rl:${key}`;

  // Get current window data
  const raw = await kv.get(kvKey);
  let timestamps: number[] = raw ? JSON.parse(raw) : [];

  // Remove expired timestamps
  timestamps = timestamps.filter((t) => t > windowStart);

  // Check limit
  if (timestamps.length >= config.maxRequests) {
    const oldestInWindow = Math.min(...timestamps);
    return {
      allowed: false,
      remaining: 0,
      resetAt: oldestInWindow + config.windowSeconds,
    };
  }

  // Record this request
  timestamps.push(now);
  await kv.put(kvKey, JSON.stringify(timestamps), {
    expirationTtl: config.windowSeconds * 2,
  });

  return {
    allowed: true,
    remaining: config.maxRequests - timestamps.length,
    resetAt: now + config.windowSeconds,
  };
}

// --- Helpers -------------------------------------------------------------

function getTier(path: string, userId: string | null): string {
  if (AGENT_PATHS.some((p) => path.startsWith(p))) return "agent_api";
  if (userId) return "authenticated";
  return "unauthenticated";
}

function rateLimitResponse(
  result: RateLimitResult,
  message: string
): Response {
  return new Response(
    JSON.stringify({
      error: message,
      retry_after: result.resetAt - Math.floor(Date.now() / 1000),
    }),
    {
      status: 429,
      headers: {
        "Content-Type": "application/json",
        "Retry-After": String(
          result.resetAt - Math.floor(Date.now() / 1000)
        ),
        "X-RateLimit-Limit": "0",
        "X-RateLimit-Remaining": "0",
        "X-RateLimit-Reset": String(result.resetAt),
      },
    }
  );
}

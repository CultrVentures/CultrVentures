/**
 * CULTR Ventures — Auth Middleware Worker
 * Runs on Cloudflare edge before requests hit Hetzner origin.
 *
 * Responsibilities:
 *   1. Validate JWT (Supabase-compatible) on protected routes
 *   2. Attach x-cultr-user-id / x-cultr-role headers for origin
 *   3. Reject expired / malformed tokens at the edge (saves origin round-trips)
 *   4. Pass-through public routes without auth
 *
 * Environment bindings (wrangler.toml):
 *   SUPABASE_JWT_SECRET  — HMAC-SHA256 secret from Supabase project settings
 *   ALLOWED_ORIGINS      — comma-separated origins for CORS
 */

export interface Env {
  SUPABASE_JWT_SECRET: string;
  ALLOWED_ORIGINS: string;
}

// Routes that don't require authentication
const PUBLIC_ROUTES = [
  "/api/health",
  "/api/v1/auth/login",
  "/api/v1/auth/register",
  "/api/v1/auth/refresh",
  "/api/v1/public",
];

// Routes that require specific roles
const ROLE_ROUTES: Record<string, string[]> = {
  "/api/v1/admin": ["admin"],
  "/api/v1/agents/deploy": ["admin", "operator"],
  "/api/v1/clients": ["admin", "operator", "consultant"],
};

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname;

    // --- CORS preflight ------------------------------------------------
    if (request.method === "OPTIONS") {
      return handleCORS(request, env);
    }

    // --- Public routes — pass through ----------------------------------
    if (isPublicRoute(path)) {
      return addCORSHeaders(await fetch(request), request, env);
    }

    // --- Extract & validate JWT ----------------------------------------
    const authHeader = request.headers.get("Authorization");
    if (!authHeader?.startsWith("Bearer ")) {
      return jsonError(401, "Missing or malformed Authorization header");
    }

    const token = authHeader.slice(7);
    let payload: JWTPayload;

    try {
      payload = await verifyJWT(token, env.SUPABASE_JWT_SECRET);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Invalid token";
      return jsonError(401, message);
    }

    // --- Check token expiry -------------------------------------------
    if (payload.exp && payload.exp < Math.floor(Date.now() / 1000)) {
      return jsonError(401, "Token expired");
    }

    // --- Role-based access control ------------------------------------
    const requiredRoles = getRequiredRoles(path);
    if (requiredRoles && !requiredRoles.includes(payload.role ?? "")) {
      return jsonError(403, `Requires role: ${requiredRoles.join(" | ")}`);
    }

    // --- Forward to origin with identity headers ----------------------
    const modifiedRequest = new Request(request);
    modifiedRequest.headers.set("X-Cultr-User-Id", payload.sub);
    modifiedRequest.headers.set("X-Cultr-Role", payload.role ?? "user");
    modifiedRequest.headers.set("X-Cultr-Email", payload.email ?? "");

    const response = await fetch(modifiedRequest);
    return addCORSHeaders(response, request, env);
  },
};

// --- JWT verification (HMAC-SHA256, Supabase-compatible) ---------------

interface JWTPayload {
  sub: string;
  email?: string;
  role?: string;
  exp?: number;
  iat?: number;
  aud?: string;
}

async function verifyJWT(token: string, secret: string): Promise<JWTPayload> {
  const parts = token.split(".");
  if (parts.length !== 3) {
    throw new Error("Malformed JWT");
  }

  const [headerB64, payloadB64, signatureB64] = parts;

  // Import HMAC key
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["verify"]
  );

  // Verify signature
  const data = new TextEncoder().encode(`${headerB64}.${payloadB64}`);
  const signature = base64UrlDecode(signatureB64);

  const valid = await crypto.subtle.verify("HMAC", key, signature, data);
  if (!valid) {
    throw new Error("Invalid signature");
  }

  // Decode payload
  const payloadJson = new TextDecoder().decode(base64UrlDecode(payloadB64));
  return JSON.parse(payloadJson) as JWTPayload;
}

function base64UrlDecode(str: string): ArrayBuffer {
  // Convert base64url to base64
  let base64 = str.replace(/-/g, "+").replace(/_/g, "/");
  while (base64.length % 4) base64 += "=";

  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

// --- Route helpers ------------------------------------------------------

function isPublicRoute(path: string): boolean {
  return PUBLIC_ROUTES.some(
    (route) => path === route || path.startsWith(route + "/")
  );
}

function getRequiredRoles(path: string): string[] | null {
  for (const [prefix, roles] of Object.entries(ROLE_ROUTES)) {
    if (path.startsWith(prefix)) return roles;
  }
  return null;
}

// --- CORS helpers -------------------------------------------------------

function handleCORS(request: Request, env: Env): Response {
  const origin = request.headers.get("Origin") ?? "";
  const allowed = env.ALLOWED_ORIGINS.split(",").map((o) => o.trim());

  if (!allowed.includes(origin) && !allowed.includes("*")) {
    return new Response(null, { status: 403 });
  }

  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": origin,
      "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
      "Access-Control-Allow-Headers":
        "Authorization, Content-Type, X-Request-Id",
      "Access-Control-Max-Age": "86400",
    },
  });
}

function addCORSHeaders(
  response: Response,
  request: Request,
  env: Env
): Response {
  const origin = request.headers.get("Origin") ?? "";
  const allowed = env.ALLOWED_ORIGINS.split(",").map((o) => o.trim());

  if (!allowed.includes(origin) && !allowed.includes("*")) {
    return response;
  }

  const newResponse = new Response(response.body, response);
  newResponse.headers.set("Access-Control-Allow-Origin", origin);
  newResponse.headers.set("Vary", "Origin");
  return newResponse;
}

// --- Error helper -------------------------------------------------------

function jsonError(status: number, message: string): Response {
  return new Response(JSON.stringify({ error: message }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

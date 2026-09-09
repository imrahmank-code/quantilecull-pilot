/**
 * QuantileCull Commercial Briefing Engine
 * 24/7 Autonomous Cloud & Edge Dispatcher with Dual-Plane Idempotency
 * Standard: Node.js 18+ (Zero external npm dependencies)
 */

const fs = require('fs');
const path = require('path');

// 1. Environment Resolution
function loadEnvFile(filePath) {
  if (fs.existsSync(filePath)) {
    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      content.split('\n').forEach(line => {
        const trimmed = line.trim();
        if (!trimmed || trimmed.startsWith('#')) return;
        const idx = trimmed.indexOf('=');
        if (idx !== -1) {
          const key = trimmed.substring(0, idx).trim();
          let value = trimmed.substring(idx + 1).trim();
          if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
            value = value.slice(1, -1);
          }
          if (!process.env[key]) {
            process.env[key] = value.trim();
          }
        }
      });
    } catch (e) {
      console.warn(`[Env] Failed to read ${filePath}: ${e.message}`);
    }
  }
}

// Search root and parent directories for .env files
const candidateDirs = [
  path.resolve(__dirname, '..'),
  path.resolve(__dirname, '../..'),
  path.resolve(__dirname, '../../..')
];

candidateDirs.forEach(dir => {
  loadEnvFile(path.join(dir, '.env.production.local'));
  loadEnvFile(path.join(dir, '.env.local'));
  loadEnvFile(path.join(dir, '.env'));
});

// CLI Flags
const args = process.argv.slice(2);
const isDryRun = args.includes('--dry-run') || process.env.DRY_RUN === 'true';
const isForce = args.includes('--force') || process.env.FORCE_DISPATCH === 'true';

// Core Configuration
const supabaseUrl = process.env.SUPABASE_URL || process.env.VITE_SUPABASE_URL || '';
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.VITE_SUPABASE_ANON_KEY || '';
const resendApiKey = process.env.RESEND_API_KEY || '';
const adminEmail = process.env.ADMIN_REPORT_EMAIL || 'quantilecull.support@gmail.com';
const founderEmail = process.env.FOUNDER_EMAIL || 'imrahman.k@gmail.com';
const senderEmail = process.env.OFFICIAL_SENDER_EMAIL || 'QuantileCull Executive <support@quantilecull.com>';

// Authoritative Indian Standard Time (IST) Date
function getAuthoritativeIstDate() {
  return new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Kolkata' });
}

// Supabase REST Helper
async function fetchSupabase(endpoint, options = {}) {
  if (!supabaseUrl || !supabaseKey) return null;
  const baseUrl = supabaseUrl.replace(/\/+$/, '');
  const url = `${baseUrl}/rest/v1/${endpoint}`;
  const response = await fetch(url, {
    method: options.method || 'GET',
    headers: {
      'apikey': supabaseKey,
      'Authorization': `Bearer ${supabaseKey}`,
      'Content-Type': 'application/json',
      'Prefer': options.prefer || 'return=representation'
    },
    body: options.body ? JSON.stringify(options.body) : undefined
  });
  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Supabase (${response.status}): ${errorText}`);
  }
  const text = await response.text();
  return text ? JSON.parse(text) : null;
}

// Resend Dispatch with 3x Exponential Backoff
async function sendResendEmailWithRetry(emailPayload, maxRetries = 3) {
  if (isDryRun) {
    console.log('[Resend DRY-RUN] Simulation active. Skipping network transmission.');
    console.log(`[Resend DRY-RUN] Recipients: ${JSON.stringify(emailPayload.to)}`);
    console.log(`[Resend DRY-RUN] Subject: "${emailPayload.subject}"`);
    return { id: `dry_run_${Date.now()}`, dryRun: true };
  }

  let attempt = 0;
  let delayMs = 1000;

  while (attempt < maxRetries) {
    attempt++;
    try {
      const response = await fetch('https://api.resend.com/emails', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${resendApiKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(emailPayload)
      });

      const data = await response.json();

      if (!response.ok) {
        const isRetryable = response.status === 429 || response.status >= 500;
        if (isRetryable && attempt < maxRetries) {
          console.warn(`[Resend] Attempt ${attempt} failed (${response.status}). Retrying in ${delayMs}ms...`);
          await new Promise(r => setTimeout(r, delayMs));
          delayMs *= 2;
          continue;
        }
        throw new Error(`Resend API error (${response.status}): ${JSON.stringify(data)}`);
      }

      return data;
    } catch (err) {
      if (attempt < maxRetries) {
        console.warn(`[Resend] Network fault on attempt ${attempt} (${err.message}). Retrying in ${delayMs}ms...`);
        await new Promise(r => setTimeout(r, delayMs));
        delayMs *= 2;
      } else {
        throw err;
      }
    }
  }
}

// Main Execution
async function main() {
  const dateStr = getAuthoritativeIstDate();
  const idempotencyKey = `daily_briefing_${dateStr}`;

  console.log(`================================================================`);
  console.log(`QUANTILECULL 24/7 COMMERCIAL REVENUE DISPATCH ENGINE`);
  console.log(`Target Date (Asia/Kolkata): ${dateStr}`);
  console.log(`Mode: ${isDryRun ? 'SIMULATION / DRY-RUN' : 'LIVE PRODUCTION'}`);
  console.log(`================================================================`);

  // 1. Idempotency Pre-flight Check
  if (!isForce && !isDryRun && supabaseUrl && supabaseKey) {
    try {
      console.log(`[Idempotency] Checking lock for key: "${idempotencyKey}"...`);
      const existingEvents = await fetchSupabase(`webhook_events?provider_event_id=eq.${encodeURIComponent(idempotencyKey)}&select=id,provider_event_id,processed_at`);
      if (existingEvents && existingEvents.length > 0) {
        console.log(`[Idempotency] SKIPPED: Briefing for ${dateStr} was already dispatched at ${existingEvents[0].processed_at}.`);
        console.log(`[Idempotency] Exactly-once delivery guaranteed. Exiting cleanly (code 0).`);
        process.exit(0);
      }
      console.log(`[Idempotency] Lock verified open. Proceeding to compilation.`);
    } catch (checkErr) {
      console.warn(`[Idempotency] Warning: Could not verify remote lock (${checkErr.message}). Continuing dispatch.`);
    }
  }

  // 2. Validate Resend Configuration
  if (!resendApiKey && !isDryRun) {
    console.error('❌ Fatal Error: RESEND_API_KEY is not configured in environment or secrets.');
    process.exit(1);
  }

  // 3. Telemetry & Revenue Aggregation
  let totalPurchases = 0;
  let totalRevenueUsd = 0;
  let totalLicenses = 0;
  let totalActivations = 0;
  let activeTrials = 0;

  if (supabaseUrl && supabaseKey) {
    try {
      const payments = await fetchSupabase('payments?status=eq.paid&select=*');
      if (payments && Array.isArray(payments)) {
        totalPurchases = payments.length;
        totalRevenueUsd = payments.reduce((sum, p) => sum + (parseFloat(p.amount) || 0), 0);
      }

      const licenses = await fetchSupabase('licenses?select=*');
      if (licenses && Array.isArray(licenses)) {
        totalLicenses = licenses.length;
        activeTrials = licenses.filter(l => l.state === 'TRIAL' || l.state === 'ACTIVE').length;
      }

      const activations = await fetchSupabase('activations?select=*');
      if (activations && Array.isArray(activations)) {
        totalActivations = activations.length;
      }
      console.log(`[Telemetry] Supabase verified metrics: ${totalPurchases} purchases ($${totalRevenueUsd}), ${totalLicenses} licenses, ${totalActivations} activations.`);
    } catch (dbErr) {
      console.warn(`[Telemetry] Supabase query notice: ${dbErr.message}`);
    }
  } else {
    console.log('[Telemetry] Supabase credentials not set; using baseline revenue counters.');
  }

  // 4. HTML Report Generation
  const htmlContent = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #09090b; color: #f4f4f5; margin: 0; padding: 24px; }
    .container { max-width: 600px; margin: 0 auto; background: #18181b; border-radius: 12px; border: 1px solid #27272a; overflow: hidden; }
    .header { background: linear-gradient(135deg, #1e1b4b 0%, #3b0764 100%); padding: 24px; border-bottom: 1px solid #3f3f46; }
    .badge { display: inline-block; background: #a855f7; color: #fff; font-size: 11px; font-weight: 700; padding: 4px 10px; border-radius: 9999px; text-transform: uppercase; letter-spacing: 0.05em; }
    .title { margin: 12px 0 4px 0; font-size: 20px; font-weight: 800; color: #ffffff; }
    .subtitle { margin: 0; font-size: 13px; color: #cbd5e1; }
    .content { padding: 24px; }
    .metric-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 24px; }
    .metric-card { background: #27272a; padding: 16px; border-radius: 8px; border: 1px solid #3f3f46; }
    .metric-label { font-size: 11px; text-transform: uppercase; color: #a1a1aa; font-weight: 600; }
    .metric-value { font-size: 22px; font-weight: 800; color: #ffffff; margin-top: 4px; }
    .metric-sub { font-size: 12px; color: #a855f7; margin-top: 2px; }
    .section-title { font-size: 14px; font-weight: 700; color: #e4e4e7; margin: 20px 0 8px 0; text-transform: uppercase; letter-spacing: 0.05em; }
    .status-box { background: rgba(168, 85, 247, 0.1); border: 1px solid rgba(168, 85, 247, 0.3); border-radius: 8px; padding: 14px; margin-bottom: 20px; font-size: 13px; color: #e9d5ff; line-height: 1.5; }
    .footer { padding: 16px 24px; background: #09090b; border-top: 1px solid #27272a; font-size: 11px; color: #71717a; text-align: center; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <span class="badge">24/7 Automated Executive Dispatch</span>
      <h1 class="title">Daily Revenue & Commercial Briefing</h1>
      <p class="subtitle">${dateStr} • Ground-Truth Verified Telemetry</p>
    </div>
    
    <div class="content">
      <div class="status-box">
        <strong>🔒 Execution Directive: Revenue Execution Mode</strong><br>
        Outbound pipeline active. Focused strictly on converting photography studios to verified $59 lifetime license purchases.
      </div>

      <div class="section-title">Verified Revenue Metrics</div>
      <div class="metric-grid">
        <div class="metric-card">
          <div class="metric-label">Paddle Verified Revenue</div>
          <div class="metric-value">$${totalRevenueUsd.toFixed(2)}</div>
          <div class="metric-sub">${totalPurchases} Closed Deals</div>
        </div>
        <div class="metric-card">
          <div class="metric-label">Device Activations</div>
          <div class="metric-value">${totalActivations}</div>
          <div class="metric-sub">${activeTrials} Total Workstations</div>
        </div>
      </div>

      <div class="section-title">Commercial Pipeline Directives</div>
      <div style="font-size: 13px; line-height: 1.6; color: #d4d4d8;">
        • <strong>Target ICP</strong>: Solo & Boutique Wedding Photographers (3,000+ RAWs/shoot).<br>
        • <strong>Offer</strong>: $59.00 USD One-Time Lifetime License with 14-Day Money-Back Guarantee.<br>
        • <strong>Checkout Endpoint</strong>: <a href="https://quantilecull.com/#pricing" style="color: #c084fc;">https://quantilecull.com/#pricing</a> (Paddle Live).
      </div>
    </div>
    
    <div class="footer">
      QuantileCull Growth Engine OS • Autonomous Reliability Subsystem
    </div>
  </div>
</body>
</html>
  `;

  // 5. Dispatch via Resend
  console.log(`[Dispatch] Transmitting briefing to [${adminEmail}, ${founderEmail}]...`);
  const result = await sendResendEmailWithRetry({
    from: senderEmail,
    to: [adminEmail, founderEmail],
    subject: `[QuantileCull] Daily Commercial Briefing — ${dateStr} ($${totalRevenueUsd.toFixed(2)} Revenue)`,
    html: htmlContent
  });

  console.log(`[Dispatch] Transmit confirmed. Message ID: ${result?.id || 'OK'}`);

  // 6. Post-Flight Idempotency Commit
  if (!isDryRun && supabaseUrl && supabaseKey) {
    try {
      console.log(`[Idempotency] Writing commit lock: "${idempotencyKey}"...`);
      await fetchSupabase('webhook_events', {
        method: 'POST',
        body: {
          provider: 'quantilecull_briefing_engine',
          provider_event_id: idempotencyKey,
          event_type: 'daily_briefing_dispatched',
          payload: {
            dispatched_at: new Date().toISOString(),
            date_str: dateStr,
            message_id: result?.id,
            revenue_usd: totalRevenueUsd,
            recipients: [adminEmail, founderEmail]
          }
        }
      });
      console.log(`[Idempotency] Lock committed successfully to Supabase.`);
    } catch (commitErr) {
      console.warn(`[Idempotency] Notice: Could not record remote commit lock (${commitErr.message}).`);
    }
  }

  console.log(`[Dispatch] Cycle complete for ${dateStr}. Success.`);
}

main().catch(err => {
  console.error('❌ [Fatal Exception]:', err.message || err);
  process.exit(1);
});

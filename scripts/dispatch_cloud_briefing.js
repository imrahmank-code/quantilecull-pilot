import { createClient } from '@supabase/supabase-js';
import { Resend } from 'resend';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');

// Helper to load env vars from .env files if process.env is empty
function loadEnvFile(filePath) {
  if (fs.existsSync(filePath)) {
    const content = fs.readFileSync(filePath, 'utf-8');
    content.split('\n').forEach(line => {
      const match = line.match(/^\s*([\w.-]+)\s*=\s*(.*)?\s*$/);
      if (match) {
        const key = match[1];
        let value = match[2] || '';
        if (value.startsWith('"') && value.endsWith('"')) value = value.slice(1, -1);
        if (value.startsWith("'") && value.endsWith("'")) value = value.slice(1, -1);
        if (!process.env[key]) {
          process.env[key] = value.trim();
        }
      }
    });
  }
}

loadEnvFile(path.join(rootDir, '.env.production.local'));
loadEnvFile(path.join(rootDir, '.env.local'));
loadEnvFile(path.join(rootDir, '.env'));

const supabaseUrl = process.env.SUPABASE_URL || process.env.VITE_SUPABASE_URL || '';
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.VITE_SUPABASE_ANON_KEY || '';
const resendApiKey = process.env.RESEND_API_KEY || '';
const adminEmail = process.env.ADMIN_REPORT_EMAIL || 'quantilecull.support@gmail.com';
const founderEmail = process.env.FOUNDER_EMAIL || 'imrahman.k@gmail.com';
const senderEmail = process.env.OFFICIAL_SENDER_EMAIL || 'QuantileCull Executive <support@quantilecull.com>';

async function run() {
  const dateStr = new Date().toISOString().split('T')[0];
  console.log(`[CloudBriefing] Starting 24/7 Cloud Revenue Dispatch for ${dateStr}...`);

  if (!resendApiKey) {
    throw new Error('Missing RESEND_API_KEY');
  }

  let totalPurchases = 0;
  let totalRevenueUsd = 0;
  let totalLicenses = 0;
  let totalActivations = 0;
  let activeTrials = 0;

  if (supabaseUrl && supabaseKey) {
    try {
      const supabase = createClient(supabaseUrl, supabaseKey);

      const { data: payments } = await supabase
        .from('payments')
        .select('*')
        .eq('status', 'paid');
      
      if (payments && Array.isArray(payments)) {
        totalPurchases = payments.length;
        totalRevenueUsd = payments.reduce((sum, p) => sum + (parseFloat(p.amount) || 0), 0);
      }

      const { data: licenses } = await supabase.from('licenses').select('*');
      if (licenses && Array.isArray(licenses)) {
        totalLicenses = licenses.length;
        activeTrials = licenses.filter(l => l.state === 'TRIAL' || l.state === 'ACTIVE').length;
      }

      const { data: activations } = await supabase.from('activations').select('*');
      if (activations && Array.isArray(activations)) {
        totalActivations = activations.length;
      }
    } catch (dbErr) {
      console.warn('[CloudBriefing] Supabase query warning:', dbErr.message);
    }
  }

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
      <span class="badge">24/7 Cloud Automated (GitHub Actions)</span>
      <h1 class="title">Daily Revenue & Commercial Briefing</h1>
      <p class="subtitle">${dateStr} • Single Source of Truth: Paddle Verified Transactions</p>
    </div>
    
    <div class="content">
      <div class="status-box">
        <strong>🔒 Execution Status: Product Implementation Frozen</strong><br>
        Revenue Execution Mode engaged. Focused strictly on converting active culler studios to verified $59 lifetime purchases.
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
      QuantileCull Growth Engine OS • Cloud Cron Autonomous Dispatcher
    </div>
  </div>
</body>
</html>
  `;

  const resend = new Resend(resendApiKey);
  const result = await resend.emails.send({
    from: senderEmail,
    to: [adminEmail, founderEmail],
    subject: `[QuantileCull Cloud] Daily Commercial Briefing — ${dateStr} ($${totalRevenueUsd.toFixed(2)} Revenue)`,
    html: htmlContent
  });

  console.log(`[CloudBriefing] Email successfully dispatched via Resend! ID: ${result.data?.id || result.id}`);
  return result;
}

run().catch((err) => {
  console.error('[CloudBriefing] Fatal Error:', err);
  process.exit(1);
});
